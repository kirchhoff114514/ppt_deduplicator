import os
import argparse
import re 
import sys
# 确保您已安装 imagehash 和 Pillow：pip install imagehash Pillow
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


def main():
    """
    主执行函数：使用 argparse 接收命令行参数。
    """
    parser = argparse.ArgumentParser(
        description="【PPT去重器】根据感知哈希（pHash）自动识别并移除智云课堂导出的重复幻灯片，生成干净的PDF。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '-i', '--input_dir', 
        type=str, 
        required=True, 
        help="【必需】存放原始 PPT 截图（例如 1.jpg, 2.jpg...）的文件夹路径。"
    )
    
    parser.add_argument(
        '-o', '--output_file', 
        type=str, 
        default="cleaned_lecture.pdf",
        help="【可选】最终生成的 PDF 文件名（含路径）。\n默认值: cleaned_lecture.pdf"
    )
    
    args = parser.parse_args()
    
    input_dir = args.input_dir
    output_pdf_path = args.output_file

    if not os.path.isdir(input_dir):
        print(f"错误：输入的文件夹路径不存在或不是一个目录: {input_dir}")
        sys.exit(1)

    print("=========================================")
    print("      🎓 PPT去重与PDF生成工具 (v1.0) 🎓")
    print("=========================================")
    print(f"   输入目录: {input_dir}")
    print(f"   输出文件: {output_pdf_path}")
    print("-" * 41)
    
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
    print("4. **操作成功！**")


if __name__ == "__main__":
    main()