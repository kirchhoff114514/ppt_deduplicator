import os
import sys
import re
# 导入 Tkinter 相关的库
from tkinter import Tk, Label, Entry, Button, filedialog, messagebox, W, E, S, N
from tkinter.ttk import Separator # Separator 需要从 ttk 导入
from typing import Optional 
from PIL import Image
import imagehash 

# (可选：如果您的Python环境没有tkinter.ttk，需要安装ttkthemes或移除Separator)

# --- 配置参数 ---
# 汉明距离阈值：用于判断两张图片是否重复。
# 值越小，要求越严格。对于 PPT 截图，8 是一個比较稳健的默认值。
HAMMING_DISTANCE_THRESHOLD = 8 

# pHash 默认使用 8x8 维度，不需要单独设置 RESIZE_DIMENSIONS，
# 因为 imagehash 库会内部处理。


def natural_sort_key(filename: str):
    """
    辅助函数：生成用于自然排序的键。
    将文件名中连续的数字视为一个整体（整数）进行比较，确保 10.jpg 在 2.jpg 之后。
    """
    # 正则表达式 r'(\d+)' 将数字部分捕获为一个组，re.split 会保留分隔符
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', filename)]


def get_image_files(input_dir: str) -> list[str]:
    """
    步骤 0: 获取所有待处理的原始 .jpg 图片文件路径，并进行自然排序。
    """
    all_files = []
    
    # 1. 筛选出所有 .jpg 文件
    for filename in os.listdir(input_dir):
        # 确保只处理文件名是纯数字后跟 .jpg 的文件
        if filename.lower().endswith('.jpg') and re.match(r'^\d+\.jpg$', filename.lower()):
            full_path = os.path.join(input_dir, filename)
            all_files.append((filename, full_path))
    
    # 2. 自然排序：使用 natural_sort_key 对文件名进行排序
    all_files.sort(key=lambda x: natural_sort_key(x[0]))
    
    # 3. 提取排序后的完整路径
    sorted_paths = [path for filename, path in all_files]
    
    return sorted_paths


def compute_perceptual_hash(image_path: str) -> imagehash.ImageHash | None:
    """
    步骤 1A & 1B: 加载图片，并计算感知哈希 (pHash)。
    """
    try:
        # 1. 打开图片
        img = Image.open(image_path)
        
        # 2. 转换为 RGB 模式（可选，但推荐用于确保一致性）
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 3. 计算 pHash
        current_hash = imagehash.phash(img)
        
        # 释放图像资源
        img.close()
        return current_hash
        
    except Exception as e:
        # 捕获文件损坏或无法读取等问题
        print(f"警告：处理文件 {image_path} 时发生错误: {e}")
        # 返回 None，由调用者处理异常情况
        return None 


def find_unique_slides(image_paths: list[str]) -> list[str]:
    """
    步骤 2: 识别并筛选出唯一的幻灯片序列。
    核心逻辑：比较当前图片与前一张**已接受**的图片之间的汉明距离。
    """
    unique_slides = []
    last_accepted_hash = None 

    total_images = len(image_paths)
    print(f"   去重阈值（汉明距离）设置为: {HAMMING_DISTANCE_THRESHOLD}")

    for i, path in enumerate(image_paths):
        current_hash = compute_perceptual_hash(path)
        
        # 检查哈希计算是否成功
        if current_hash is None:
            # 如果无法计算哈希，跳过此文件
            continue
        
        if last_accepted_hash is None:
            # 1. 第一次循环：接受第一张图
            unique_slides.append(path)
            last_accepted_hash = current_hash
        else:
            # 2. 比较：计算汉明距离
            hamming_distance = current_hash - last_accepted_hash
            
            if hamming_distance > HAMMING_DISTANCE_THRESHOLD:
                # 3. 如果距离大于阈值，说明是新的一页 PPT，接受它
                unique_slides.append(path)
                last_accepted_hash = current_hash
            # else: 距离小于等于阈值，说明是重复，跳过

        # 打印进度（每处理 50 张图片或结束时打印）
        if (i + 1) % 50 == 0 or (i + 1) == total_images:
            sys.stdout.write(f"\r   进度: {i + 1} / {total_images} 张已处理. 当前已保留 {len(unique_slides)} 张唯一幻灯片.")
            sys.stdout.flush()
            
    sys.stdout.write('\n') # 确保进度条后换行
    return unique_slides


def create_pdf_from_images(image_paths: list[str], output_path: str):
    """
    步骤 3: 将筛选后的图片序列拼接成最终的 PDF 文件。
    """
    if not image_paths:
        print("警告：没有图片可以生成 PDF，跳过生成步骤。")
        return

    try:
        # 1. 打开第一张图片作为 PDF 的起始页
        first_image_path = image_paths[0]
        img_base = Image.open(first_image_path).convert('RGB')
        
        img_list = []
        # 2. 收集剩下的图片对象
        for path in image_paths[1:]:
            img = Image.open(path).convert('RGB')
            img_list.append(img)
            
        # 3. 保存为 PDF
        img_base.save(
            output_path, 
            "PDF", 
            resolution=100.0,
            save_all=True, 
            append_images=img_list
        )
        
        # 4. 释放资源
        img_base.close()
        for img in img_list:
            img.close()
            
    except Exception as e:
        print(f"\n致命错误：生成 PDF 时发生错误: {e}")
        print("请检查图片文件是否完整或 PIL 库是否能处理这些图片。")
        raise # 抛出异常，让用户知道失败

def extract_input_features(input_dir: str) -> str:
    """
    根据输入的路径，提取倒数第三级和倒数第二级目录作为核心特征，
    以实现文件名简短且具有辨识度。
    """
    # 规范化路径并移除末尾斜杠
    normalized_path = os.path.normpath(input_dir)
    # 按操作系统分隔符分割，并过滤掉空字符串（防止双斜杠等问题）
    parts = [part for part in normalized_path.split(os.sep) if part]
    
    # 排除驱动器号（如 'C:'），只保留目录名称
    if parts and parts[0].endswith(':'):
        parts = parts[1:] 

    # ----------------------------------------------------
    # 核心提取逻辑：专注于路径的尾部
    # ----------------------------------------------------
    
    feature_parts = []
    
    # 倒数第一级 (Last part, e.g., 'ppt_images')
    last_part = parts[-1] if parts else ""
    
    # 倒数第二级 (Second-to-last part, e.g., '2025-09-25第3-5节')
    second_last_part = parts[-2] if len(parts) >= 2 else ""

    # 倒数第三级 (Third-to-last part, e.g., '设计与制造Ⅲ')
    third_last_part = parts[-3] if len(parts) >= 3 else ""

    # 1. 识别并忽略通用的末尾目录 (如 'ppt_images')
    generic_names = ['ppt_images', 'images', 'screenshots', 'temp', 'files']
    
    if last_part.lower() in generic_names:
        # 如果末尾是通用名，我们用倒数第二级和倒数第三级
        
        # 提取倒数第三级（如 课程名）
        if third_last_part:
            feature_parts.append(third_last_part)
            
        # 提取倒数第二级（如 日期/节次）
        if second_last_part:
            # 确保不重复添加
            if not feature_parts or feature_parts[-1] != second_last_part:
                feature_parts.append(second_last_part)
                
    else:
        # 如果末尾不是通用名，认为末尾两级都重要
        
        # 提取倒数第二级
        if second_last_part:
            feature_parts.append(second_last_part)
            
        # 提取倒数第一级
        if last_part:
            # 确保不重复添加
            if not feature_parts or feature_parts[-1] != last_part:
                feature_parts.append(last_part)
                
    # ----------------------------------------------------
    
    if not feature_parts:
        # 如果路径太短，至少保留最后一个目录名
        return parts[-1] if parts else "Unknown"

    # 将提取出的部分用下划线连接，并清理文件名中可能不允许的字符
    safe_name = "_".join(feature_parts)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name) # 替换非法字符
    
    # 移除首尾可能出现的下划线，防止路径分割错误导致
    return safe_name.strip('_')


class PPTDeduplicatorApp:
    def __init__(self, master):
        self.master = master
        master.title("🎓 智云课堂 PPT 去重工具 (v0.0)")
        
        # 内部变量
        self.input_dir = ""
        self.output_dir = ""

        # --- 布局配置 ---
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)
        
        # --- 1. 输入路径设置 ---
        Label(master, text="输入文件夹 (原始截图):").grid(row=0, column=0, sticky=W, padx=10, pady=(10, 2))
        
        self.input_entry = Entry(master, width=60)
        self.input_entry.grid(row=1, column=0, sticky=W+E, padx=10, pady=(0, 5))
        
        input_button = Button(master, text="浏览...", command=self.browse_input)
        input_button.grid(row=1, column=1, sticky=W, padx=5, pady=(0, 5))

        # --- 2. 分隔线 ---
        Separator(master, orient='horizontal').grid(row=2, column=0, columnspan=2, sticky=W+E, padx=10, pady=5)

        # --- 3. 输出路径设置 ---
        Label(master, text="输出目录 (PDF存放地):").grid(row=3, column=0, sticky=W, padx=10, pady=(5, 2))
        
        self.output_entry = Entry(master, width=60)
        self.output_entry.grid(row=4, column=0, sticky=W+E, padx=10, pady=(0, 10))
        
        output_button = Button(master, text="浏览...", command=self.browse_output)
        output_button.grid(row=4, column=1, sticky=W, padx=5, pady=(0, 10))
        
        # --- 4. 运行按钮 ---
        run_button = Button(master, text="✨ 生成 PDF (开始去重) ✨", command=self.run_deduplication, fg="white", bg="#209865")
        run_button.grid(row=5, column=0, columnspan=2, sticky=W+E, padx=10, pady=10)

        # --- 5. 状态/日志区域 ---
        self.status_label = Label(master, text="状态: 等待操作...")
        self.status_label.grid(row=6, column=0, columnspan=2, sticky=W, padx=10, pady=(5, 10))
        
        
    def browse_input(self):
        """打开对话框，选择输入文件夹"""
        folder_selected = filedialog.askdirectory(title="选择包含原始 PPT 截图的文件夹")
        if folder_selected:
            self.input_dir = folder_selected
            self.input_entry.delete(0, 'end')
            self.input_entry.insert(0, self.input_dir)
            self.status_label.config(text=f"状态: 输入路径已设置。")
            
    def browse_output(self):
        """打开对话框，选择输出目录"""
        folder_selected = filedialog.askdirectory(title="选择生成 PDF 文件存放的目录")
        if folder_selected:
            self.output_dir = folder_selected
            self.output_entry.delete(0, 'end')
            self.output_entry.insert(0, self.output_dir)
            self.status_label.config(text=f"状态: 输出路径已设置。")

    def run_deduplication(self):
        """点击“生成”按钮时执行的核心逻辑"""
        input_dir = self.input_entry.get()
        output_dir = self.output_entry.get()

        if not os.path.isdir(input_dir) or not os.path.isdir(output_dir):
            messagebox.showerror("错误", "请输入有效的输入文件夹和输出目录。")
            return

        try:
            # 确保输出目录存在，如果不存在则创建
            os.makedirs(output_dir, exist_ok=True)
            
            # --- 1. 文件名生成 ---
            self.status_label.config(text="状态: 正在生成文件名...")
            self.master.update()
            
            base_filename = extract_input_features(input_dir)
            output_pdf_filename = f"{base_filename}_Cleaned.pdf"
            output_pdf_path = os.path.join(output_dir, output_pdf_filename)

            # print(f"输入: {input_dir}")
            # print(f"输出文件: {output_pdf_path}")
            
            # --- 2. 获取文件并排序 ---
            self.status_label.config(text="状态: 1/3 正在获取并排序图片...")
            self.master.update()
            
            all_image_paths = get_image_files(input_dir)
            if not all_image_paths:
                messagebox.showinfo("完成", "未找到任何图片文件，操作取消。")
                return

            # --- 3. 筛选去重 ---
            self.status_label.config(text=f"状态: 2/3 正在处理 {len(all_image_paths)} 张图片，开始去重...")
            self.master.update()
            
            unique_paths = find_unique_slides(all_image_paths)

            # --- 4. 生成 PDF ---
            self.status_label.config(text=f"状态: 3/3 正在生成 PDF ({len(unique_paths)} 页)...")
            self.master.update()
            
            create_pdf_from_images(unique_paths, output_pdf_path)

            # --- 5. 成功提示 ---
            self.status_label.config(text="状态: 🎉 成功！PDF 已生成。", fg="green")
            messagebox.showinfo("成功", f"PPT 去重完成！\n文件已保存至: {output_pdf_path}")

        except Exception as e:
            self.status_label.config(text=f"状态: ❌ 运行失败。", fg="red")
            # 使用更友好的错误提示
            messagebox.showerror("运行错误", f"处理过程中发生错误: {e}\n请检查权限或文件是否损坏。")
            # 同时在控制台打印详细错误
            import traceback
            traceback.print_exc(file=sys.stdout)


if __name__ == "__main__":
    # --- 启动 Tkinter GUI ---
    root = Tk()
    app = PPTDeduplicatorApp(root)
    # 保持窗口大小可调整
    root.resizable(True, False) 
    root.mainloop()