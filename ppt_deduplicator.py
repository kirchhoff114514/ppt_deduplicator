import os
import argparse
import re 
import sys
from typing import Optional 
from PIL import Image
import imagehash 

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
    根据输入的路径，提取具有辨识度的特征，用于构造输出文件名。
    """
    # 规范化路径，移除末尾斜杠，并按操作系统分隔符分割
    parts = input_dir.rstrip(os.sep).split(os.sep)
    
    # 假设：倒数第一级通常是通用的 'ppt_images' 或类似物，可忽略
    # 倒数第二级和第三级最可能是 '日期/节次' 和 '课程名'
    
    feature_parts = []
    
    # 尝试提取倒数第二级（如 '2025-09-18第3-5节'）
    if len(parts) >= 2:
        # 如果倒数第一级是通用名（如 ppt_images, images），则取倒数第二级
        if parts[-1].lower() in ['ppt_images', 'images', 'screenshots']:
             feature_parts.append(parts[-2])
             
             # 尝试提取倒数第三级（如 '设计与制造Ⅲ'）
             if len(parts) >= 3:
                 feature_parts.insert(0, parts[-3])
        else:
             # 如果倒数第一级不是通用名，则认为它包含重要信息
             feature_parts.append(parts[-1])
             if len(parts) >= 2:
                 feature_parts.insert(0, parts[-2])
    elif len(parts) == 1:
        # 只有一级路径，直接使用它
        feature_parts.append(parts[-1])

    if not feature_parts:
        return "Unknown" # 提取失败的备用名称
        
    # 将提取出的部分用下划线连接，并清理文件名中可能不允许的字符
    safe_name = "_".join(feature_parts)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name) # 替换非法字符
    
    return safe_name


def main():
    """
    主执行函数：使用 argparse 接收命令行参数并处理文件路径。
    """
    parser = argparse.ArgumentParser(
        description="【PPT去重器】根据感知哈希（pHash）自动识别并移除智云课堂导出的重复幻灯片。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '-i', '--input_dir', 
        type=str, 
        required=True, 
        help="【必需】存放原始 PPT 截图的文件夹路径。"
    )
    
    # 修改参数：现在接受输出目录
    parser.add_argument(
        '-d', '--output_dir', 
        type=str, 
        default=".", # 默认输出到当前运行目录
        help="【可选】最终 PDF 文件的存放目录。\n默认值: 当前运行目录 (./)"
    )
    
    args = parser.parse_args()
    
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isdir(input_dir):
        print(f"错误：输入的文件夹路径不存在或不是一个目录: {input_dir}")
        sys.exit(1)
        
    # 确保输出目录存在，如果不存在则创建
    os.makedirs(output_dir, exist_ok=True)


    # --- 新增逻辑：文件名生成 ---
    base_filename = extract_input_features(input_dir)
    output_pdf_filename = f"{base_filename}_Cleaned.pdf"
    output_pdf_path = os.path.join(output_dir, output_pdf_filename)
    # --------------------------

    print("=========================================")
    print("      🎓 PPT去重与PDF生成工具 (v1.1) 🎓")
    print("=========================================")
    print(f"   输入目录: {input_dir}")
    print(f"   输出目录: {output_dir}")
    print(f"   生成文件名: {output_pdf_filename}")
    print("-" * 41)
    
    # 1. 获取文件并排序
    all_image_paths = get_image_files(input_dir)
    # ... (其余逻辑保持不变) ...

    # 1. 获取文件并排序
    all_image_paths = get_image_files(input_dir)
    print(f"1. 成功获取 {len(all_image_paths)} 张原始图片文件 (.jpg)，已按自然顺序排序。")
    
    if not all_image_paths:
        print("未找到任何符合要求的 .jpg 文件，程序退出。")
        return

    # 2. 筛选
    print("2. 正在进行重复幻灯片筛选...")
    unique_paths = find_unique_slides(all_image_paths)
    print(f"   筛选完成。最终确定 {len(unique_paths)} 张非重复幻灯片。")

    # 3. 生成 PDF
    print(f"3. 正在生成 PDF 文件...")
    create_pdf_from_images(unique_paths, output_pdf_path)
    print(f"4. **操作成功！** 文件保存在: {output_pdf_path}")


if __name__ == "__main__":
    main()