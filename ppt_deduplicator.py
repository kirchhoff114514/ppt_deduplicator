import os
import sys
import re
from tkinter import Tk, Label, Entry, Button, filedialog, messagebox, W, E, S, N
from tkinter.ttk import Separator
from PIL import Image
import imagehash

# --- 优化后的配置参数 ---
# 1. 动画阈值：如果差异大于此值但小于换页阈值，认为是同一页 PPT 增加了新内容（如文字变多）
# 我们会用“更全”的图替换掉旧图。
ANIMATION_THRESHOLD = 2 

# 2. 换页阈值：如果差异大于此值，认为进入了完全不同的一页 PPT。
# 此时我们会把上一页的“最终态”保存下来。
NEW_SLIDE_THRESHOLD = 20 


def natural_sort_key(filename: str):
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', filename)]


def get_image_files(input_dir: str) -> list[str]:
    all_files = []
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')) and re.search(r'\d+', filename):
            full_path = os.path.join(input_dir, filename)
            all_files.append((filename, full_path))
    all_files.sort(key=lambda x: natural_sort_key(x[0]))
    return [path for filename, path in all_files]


def compute_perceptual_hash(image_path: str) -> imagehash.ImageHash | None:
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return imagehash.phash(img)
    except Exception as e:
        print(f"警告：处理文件 {image_path} 时发生错误: {e}")
        return None 


def find_unique_slides(image_paths: list[str]) -> list[str]:
    """
    核心逻辑升级：候选区替换策略 (Buffer Replacement Strategy)
    解决 1 -> 1,2 -> 1,2,3 的动画叠加问题
    """
    if not image_paths:
        return []

    final_slides = []
    
    # 初始化：第一张图作为第一个“候选人”
    candidate_path = image_paths[0]
    candidate_hash = compute_perceptual_hash(candidate_path)
    
    total_images = len(image_paths)
    print(f"   判定逻辑：双阈值过滤（动画阈值:{ANIMATION_THRESHOLD}, 换页阈值:{NEW_SLIDE_THRESHOLD}）")

    for i in range(1, total_images):
        current_path = image_paths[i]
        current_hash = compute_perceptual_hash(current_path)
        
        if current_hash is None or candidate_hash is None:
            continue
        
        # 计算当前图片与“候选人”之间的距离
        distance = current_hash - candidate_hash
        
        if distance > NEW_SLIDE_THRESHOLD:
            # --- 情况 A：距离很大，判定为【换页了】 ---
            # 1. 把之前的候选人（即上一页的最全形态）存入结果
            final_slides.append(candidate_path)
            # 2. 把当前图设为新的候选人
            candidate_path = current_path
            candidate_hash = current_hash
            
        elif distance > ANIMATION_THRESHOLD:
            # --- 情况 B：距离中等，判定为【同一页的动画叠加】 ---
            # 这种情况下，1,2 覆盖 1， 1,2,3 覆盖 1,2
            # 我们不保存到 final_slides，只是更新候选人，让它保持为“最新、最全”的状态
            candidate_path = current_path
            candidate_hash = current_hash
            
        # --- 情况 C：距离极小，判定为【重复帧】，不做任何操作，继续找下一张 ---

        # 打印进度
        if (i + 1) % 50 == 0 or (i + 1) == total_images:
            sys.stdout.write(f"\r   进度: {i + 1} / {total_images} 张已处理. 已捕获 {len(final_slides) + 1} 页 PPT.")
            sys.stdout.flush()

    # 循环结束后，最后留在手中的候选人必定是最后一页的最终形态，必须加入
    final_slides.append(candidate_path)
    
    print("\n   去重完成！")
    return final_slides


def create_pdf_from_images(image_paths: list[str], output_path: str):
    if not image_paths:
        return

    try:
        img_objects = []
        for path in image_paths:
            img = Image.open(path).convert('RGB')
            img_objects.append(img)
            
        if img_objects:
            img_objects[0].save(
                output_path, 
                "PDF", 
                resolution=100.0,
                save_all=True, 
                append_images=img_objects[1:]
            )
            
        for img in img_objects:
            img.close()
            
    except Exception as e:
        print(f"\n致命错误：生成 PDF 时发生错误: {e}")
        raise


def extract_input_features(input_dir: str) -> str:
    normalized_path = os.path.normpath(input_dir)
    parts = [part for part in normalized_path.split(os.sep) if part]
    if parts and parts[0].endswith(':'):
        parts = parts[1:] 
    
    if len(parts) >= 2:
        safe_name = f"{parts[-2]}_{parts[-1]}"
    elif parts:
        safe_name = parts[-1]
    else:
        safe_name = "Cleaned_PPT"
        
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name)
    return safe_name.strip('_')


class PPTDeduplicatorApp:
    def __init__(self, master):
        self.master = master
        master.title("🎓 智云课堂 PPT 深度去重版 (v1.2.0)")
        
        self.input_dir = ""
        self.output_dir = ""

        # UI 构建
        Label(master, text="输入文件夹 (原始截图):").grid(row=0, column=0, sticky=W, padx=10, pady=(10, 2))
        self.input_entry = Entry(master, width=60)
        self.input_entry.grid(row=1, column=0, sticky=W+E, padx=10, pady=(0, 5))
        Button(master, text="浏览...", command=self.browse_input).grid(row=1, column=1, sticky=W, padx=5, pady=(0, 5))

        Separator(master, orient='horizontal').grid(row=2, column=0, columnspan=2, sticky=W+E, padx=10, pady=5)

        Label(master, text="输出目录 (PDF存放地):").grid(row=3, column=0, sticky=W, padx=10, pady=(5, 2))
        self.output_entry = Entry(master, width=60)
        self.output_entry.grid(row=4, column=0, sticky=W+E, padx=10, pady=(0, 10))
        Button(master, text="浏览...", command=self.browse_output).grid(row=4, column=1, sticky=W, padx=5, pady=(0, 10))
        
        self.run_button = Button(master, text="✨ 开始深度去重并生成 PDF ✨", command=self.run_deduplication, fg="white", bg="#209865", font=("微软雅黑", 10, "bold"))
        self.run_button.grid(row=5, column=0, columnspan=2, sticky=W+E, padx=10, pady=10)

        self.status_label = Label(master, text="状态: 等待中...", fg="blue")
        self.status_label.grid(row=6, column=0, columnspan=2, sticky=W, padx=10, pady=(5, 10))
        
    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_entry.delete(0, 'end')
            self.input_entry.insert(0, folder)
            
    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, 'end')
            self.output_entry.insert(0, folder)

    def run_deduplication(self):
        input_dir = self.input_entry.get()
        output_dir = self.output_entry.get()

        if not os.path.isdir(input_dir) or not os.path.isdir(output_dir):
            messagebox.showerror("错误", "请输入有效的路径。")
            return

        try:
            self.run_button.config(state="disabled", text="正在处理，请勿关闭...")
            self.status_label.config(text="状态: 1/3 正在加载图片列表...", fg="black")
            self.master.update()
            
            all_image_paths = get_image_files(input_dir)
            if not all_image_paths:
                messagebox.showinfo("提示", "该文件夹内没有找到有效的图片文件。")
                self.run_button.config(state="normal", text="✨ 开始深度去重并生成 PDF ✨")
                return

            self.status_label.config(text=f"状态: 2/3 正在识别动画与翻页 (共{len(all_image_paths)}张)...")
            self.master.update()
            
            # 调用新的去重逻辑
            unique_paths = find_unique_slides(all_image_paths)

            self.status_label.config(text=f"状态: 3/3 正在生成 PDF (共 {len(unique_paths)} 页)...")
            self.master.update()
            
            base_filename = extract_input_features(input_dir)
            output_pdf_path = os.path.join(output_dir, f"{base_filename}_FullContent.pdf")
            create_pdf_from_images(unique_paths, output_pdf_path)

            self.status_label.config(text="状态: 🎉 任务成功完成！", fg="green")
            messagebox.showinfo("成功", f"处理完成！\n已自动合并动画，共保留 {len(unique_paths)} 页。\n保存至: {output_pdf_path}")

        except Exception as e:
            self.status_label.config(text=f"状态: ❌ 出错了。", fg="red")
            messagebox.showerror("运行错误", str(e))
        finally:
            self.run_button.config(state="normal", text="✨ 开始深度去重并生成 PDF ✨")


if __name__ == "__main__":
    root = Tk()
    app = PPTDeduplicatorApp(root)
    root.resizable(True, False) 
    root.mainloop()