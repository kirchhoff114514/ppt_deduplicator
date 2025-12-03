# 🎓 ZJU 智云课堂 PPT 去重工具 (PPT Deduplicator)

## 🌟 项目简介



本项目是针对 [GitHub - PeiPei233/zju-learning-assistant](https://github.com/PeiPei233/zju-learning-assistant) 工具的补充。`zju-learning-assistant` 可快速下载智云课堂录像中的课件截图，但由于智云课堂的录屏机制，这些截图经常包含多张重复的 PPT 页面。

本工具旨在通过图像处理，**自动识别并移除这些重复的幻灯片帧**，最终生成一个干净、有序、体积更小的课件 PDF 文件。



## 🚀 使用指南 (Release 版本)

如果您是从 **GitHub Releases** 下载的工具，无需安装 Python 环境，只需以下几步：

1.  **下载：** 访问 [您的 GitHub Releases 页面链接]()，下载最新版本的 **`PPTDeduplicator.exe`** 文件。
2.  **启动：** 双击运行 `PPTDeduplicator.exe`。
3.  **前置步骤 (使用 zju-learning-assistant):**
    * 首先使用 **`zju-learning-assistant`** 下载智云课堂的课件截图。
    * **记住**下载完成后的图片所在的文件夹路径，例如：`C:\Users\Maxwell\Downloads\设计与制造Ⅲ\2025-09-18第3-5节\ppt_images`。
4.  **配置路径：**
    * 在 **本工具** 中，点击 **“输入文件夹”** 旁的 **“浏览...”** 按钮，选择上面记住的路径（如 `...\ppt_images`）。
    * 点击 **“输出目录”** 旁的 **“浏览...”** 按钮，选择 PDF 文件希望存放的位置（可任意选择）。
5.  **运行：** 点击 **“生成 PDF (开始去重)”** 按钮，程序将自动完成去重和 PDF 生成。
6.  **查看结果：** 最终文件将以智能命名保存在您指定的输出目录中。

### ⚠️ 注意事项

1.  **成功提示：** 程序 **GUI 最底下的状态栏** 会反映 PDF 是否成功输出。请留意该状态栏的信息。
2.  **避免重复工作：** 建议您在 `zju-learning-assistant` 的设置中，**关闭“自动导出为 PDF”** 选项，避免生成未经去重的冗余 PDF 文件。

## ✨ 核心功能

* **图形用户界面 (GUI):** 基于 Tkinter 实现，操作直观，无需命令行，用户体验友好。
* **智能去重：** 使用 **感知哈希 (pHash)** 算法和汉明距离，根据图片的视觉指纹判断相似度，精确识别并移除连续的重复页面。
* **智能命名：** 自动提取输入文件夹路径中的关键信息（如“课程名称”和“日期/节次”）来构造输出文件名，文件名简洁且具有高度辨识度。
* **PDF 一键生成：** 将去重后的图片序列按正确顺序合并为高质量的 PDF 文档。
* **自然排序：** 确保文件名如 `1.jpg, 2.jpg, 10.jpg` 能被正确排序和处理。

## 🔧 开发环境与依赖

本项目基于 Python 开发。

### 环境要求

* Python **3.6** 及以上版本 (推荐使用 Python 3.10+)。

### 依赖库安装

本项目依赖 `imagehash` 和 `Pillow`。请使用 `pip` 进行安装：

```bash
# 激活您的虚拟环境
conda activate ppt_deduplicator 

# 安装依赖
pip install imagehash Pillow