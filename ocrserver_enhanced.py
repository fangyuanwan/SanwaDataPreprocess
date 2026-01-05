"""
增强版OCR服务器 - 带动态Prompt和实时Median计算
Enhanced OCR Server with Dynamic Prompts and Real-time Median Calculation

特性 Features:
1. 根据ROI类型动态生成Prompt
2. 实时计算并使用Median值作为上下文
3. 自适应精度控制
4. 完整的调试输出
"""

import sys
import time
import json
import csv
import cv2
import ollama
import os
import numpy as np
import pandas as pd
import concurrent.futures
import threading
from datetime import datetime, timedelta
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import defaultdict

# 导入配置
from config_pipeline import *

# ================= 全局Median追踪器 =================
class MedianTracker:
    """实时追踪每个ROI的Median值"""
    def __init__(self):
        self.data = defaultdict(list)  # roi_id -> [values]
        self.medians = {}  # roi_id -> current_median
        self.lock = threading.Lock()
        self.min_samples = 5  # 最少样本数才计算median
        
    def add_value(self, roi_id, value, data_type):
        """添加新值并更新median"""
        with self.lock:
            # 只对数值类型计算median
            if data_type not in ['INTEGER', 'FLOAT']:
                return
            
            try:
                num_val = float(value)
                if num_val > 0:  # 忽略0值（可能是缺陷）
                    self.data[roi_id].append(num_val)
                    
                    # 限制缓存大小，只保留最近100个值
                    if len(self.data[roi_id]) > 100:
                        self.data[roi_id] = self.data[roi_id][-100:]
                    
                    # 更新median
                    if len(self.data[roi_id]) >= self.min_samples:
                        self.medians[roi_id] = np.median(self.data[roi_id])
            except:
                pass
    
    def get_median(self, roi_id):
        """获取ROI的当前median值"""
        with self.lock:
            return self.medians.get(roi_id, None)
    
    def get_stats(self, roi_id):
        """获取ROI的统计信息"""
        with self.lock:
            if roi_id not in self.data or len(self.data[roi_id]) < self.min_samples:
                return None
            values = self.data[roi_id]
            return {
                'median': np.median(values),
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'count': len(values)
            }

# 全局median追踪器
median_tracker = MedianTracker()
print_lock = threading.Lock()

# ================= 增强的GPU处理器 =================
class EnhancedGPUHandler(FileSystemEventHandler):
    def __init__(self, rois):
        self.rois = rois
        self.processed_count = 0
        
    def on_created(self, event):
        if not event.is_directory: 
            self.process_new_file(Path(event.src_path))
    
    def on_moved(self, event):
        if not event.is_directory: 
            self.process_new_file(Path(event.dest_path))
    
    def process_new_file(self, file_path: Path):
        """处理新图像文件"""
        if file_path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp'}: 
            return
        if file_path.name.startswith("."): 
            return
        
        self.processed_count += 1
        print(f"\n⚡ [{self.processed_count}] Processing: {file_path.name}")
        
        try:
            relative_path = file_path.relative_to(SOURCE_DIR)
        except ValueError:
            relative_path = Path(file_path.name)
        
        relative_parent = relative_path.parent
        
        # 创建调试目录
        image_folder_name = file_path.stem
        target_image_folder = STAGE_1_OCR / "debug_crops" / relative_parent / image_folder_name
        target_image_folder.mkdir(parents=True, exist_ok=True)
        
        self.run_parallel_pipeline(file_path, target_image_folder, relative_parent)
    
    def parse_filename_time(self, filename):
        """从文件名解析时间"""
        try:
            name_only = filename.rsplit('.', 1)[0]
            dt = datetime.strptime(name_only, "%Y-%m-%d %H.%M.%S")
            return dt.isoformat() + "Z"
        except: 
            return filename
    
    def parse_machine_time(self, text_str):
        """解析机器时间戳"""
        if not text_str or len(text_str) < 5 or "NA" in text_str: 
            return ""
        try:
            clean = text_str.replace("\n", " ").replace("|", "/").strip()
            dt_local = datetime.strptime(clean, "%b/%d/%y %H:%M:%S")
            dt_utc = dt_local - timedelta(hours=8)
            return dt_utc.isoformat() + "Z"
        except: 
            return text_str
    
    def analyze_image_colors(self, img):
        """
        分析图像颜色和亮度
        返回: (is_valid, color_info)
        """
        if img is None or img.size == 0:
            return False, "Empty image"
        
        # 转换到HSV色彩空间用于颜色检测
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 检查整体亮度
        mean_brightness = np.mean(gray)
        
        # 如果图像极暗（几乎全黑）
        if mean_brightness < DARKNESS_THRESHOLD:
            # 检查是否有任何明亮的文本
            bright_pixels = np.sum(gray > 100)  # 亮度>100的像素
            if bright_pixels < (img.size * 0.01):  # 少于1%的亮像素
                return False, "Too dark - no visible text"
        
        # 颜色检测
        color_info = {
            'has_red': False,
            'has_green': False, 
            'has_white': False,
            'dominant_color': 'unknown',
            'background': 'dark' if mean_brightness < 100 else 'bright'
        }
        
        # 红色检测 (H: 0-10 或 170-180, S: 50-255, V: 50-255)
        red_mask1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
        red_pixels = np.sum(red_mask1) + np.sum(red_mask2)
        
        # 绿色检测 (H: 40-80, S: 50-255, V: 50-255)
        green_mask = cv2.inRange(hsv, np.array([40, 50, 50]), np.array([80, 255, 255]))
        green_pixels = np.sum(green_mask)
        
        # 白色检测 (S: 0-30, V: 200-255) - 高亮度，低饱和度
        white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 30, 255]))
        white_pixels = np.sum(white_mask)
        
        # 判定主要颜色（像素数占比）
        total_pixels = img.shape[0] * img.shape[1] * 255
        red_ratio = red_pixels / total_pixels
        green_ratio = green_pixels / total_pixels
        white_ratio = white_pixels / total_pixels
        
        color_info['has_red'] = red_ratio > 0.01  # 超过1%
        color_info['has_green'] = green_ratio > 0.01
        color_info['has_white'] = white_ratio > 0.01
        
        # 确定主导颜色
        if red_ratio > green_ratio and red_ratio > white_ratio:
            color_info['dominant_color'] = 'red'
        elif green_ratio > white_ratio:
            color_info['dominant_color'] = 'green'
        elif white_ratio > 0.01:
            color_info['dominant_color'] = 'white'
        
        return True, color_info
    
    def is_image_too_dark(self, img):
        """检查图像是否太暗（保持向后兼容）"""
        is_valid, info = self.analyze_image_colors(img)
        return not is_valid
    
    def ask_ollama_with_context(self, image_path, roi_id, color_info, attempt=1):
        """
        使用上下文信息调用Ollama
        
        Args:
            image_path: 图像路径
            roi_id: ROI标识符
            color_info: 颜色分析信息 (dict with has_red, has_green, has_white, dominant_color, background)
            attempt: 尝试次数（1=初始，2=带median修正）
        """
        roi_type = get_roi_type(roi_id)
        
        # 获取median上下文
        median_val = median_tracker.get_median(roi_id)
        
        # 生成基础prompt
        if attempt == 1:
            prompt = get_prompt(roi_id, 'initial', median_value=median_val)
        else:
            prompt = get_prompt(roi_id, 'correction', median_value=median_val)
        
        # 根据颜色信息增强prompt
        color_hint = self._generate_color_hint(roi_type, color_info)
        if color_hint:
            prompt = prompt + "\n\n" + color_hint
        
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL_3B,
                messages=[{
                    'role': 'user', 
                    'content': prompt, 
                    'images': [str(image_path)]
                }],
                options={
                    'temperature': 0.0,  # 确定性输出
                    'num_predict': 30
                }
            )
            raw = response['message']['content'].strip()
            
            # 清理输出（传递颜色信息）
            clean = self.post_process_ocr(raw, roi_type, color_info)
            
            return clean
            
        except Exception as e:
            with print_lock:
                print(f"  [OCR Error {roi_id}]: {e}")
            return "NA"
    
    def _generate_color_hint(self, roi_type, color_info):
        """
        根据颜色信息生成额外的prompt提示
        """
        hints = []
        
        # 背景信息
        if color_info.get('background') == 'dark':
            hints.append("🌙 DARK BACKGROUND IMAGE:")
        
        # 根据ROI类型和颜色信息生成提示
        if roi_type == 'STATUS':
            if color_info.get('has_red'):
                hints.append("  • RED text detected → This usually means 'NG' (fail/defect)")
                hints.append("  • If you see red text → Output: NG")
            if color_info.get('has_green'):
                hints.append("  • GREEN text detected → This usually means 'OK' (pass/good)")
                hints.append("  • If you see green text → Output: OK")
            
            # 颜色规则
            hints.append("\nColor Rule for STATUS:")
            hints.append("  - RED text = NG")
            hints.append("  - GREEN text = OK")
            hints.append("  - Trust the COLOR more than the text if ambiguous")
        
        elif roi_type in ['INTEGER', 'FLOAT']:
            if color_info.get('has_white'):
                hints.append("  • WHITE text detected → This is the number you need to read")
            
            if color_info.get('background') == 'dark':
                hints.append("\nReading numbers on DARK background:")
                hints.append("  - Look for WHITE or BRIGHT colored digits")
                hints.append("  - Ignore dim or barely visible marks")
                hints.append("  - The main number is usually in WHITE")
                
                # 如果是FLOAT，额外提醒小数点
                if roi_type == 'FLOAT':
                    hints.append("  - Look carefully for the WHITE decimal point '.'")
                    hints.append("  - Decimal point may be small but should be visible")
        
        return "\n".join(hints) if hints else ""
    
    def post_process_ocr(self, raw_text, roi_type, color_info=None):
        """
        后处理OCR结果
        
        Args:
            raw_text: 原始OCR文本
            roi_type: ROI类型
            color_info: 颜色信息（可选）
        """
        # 移除markdown和HTML标签
        import re
        text = re.sub(r'<[^>]+>', '', raw_text)
        text = text.replace('```', '').replace('`', '').strip()
        text = re.sub(r'^(Output:|Result:)', '', text, flags=re.IGNORECASE).strip()
        
        if roi_type == 'STATUS':
            # 标准化状态值
            upper = text.upper()
            
            # 如果有颜色信息，优先使用颜色判断
            if color_info:
                if color_info.get('has_red') and color_info.get('dominant_color') == 'red':
                    # 如果检测到红色，很可能是NG
                    if 'NG' in upper or 'N' in upper or 'G' in upper:
                        return 'NG'
                    # 即使文本不清楚，红色也倾向于NG
                    if not ('OK' in upper or 'O' in upper):
                        return 'NG'
                
                if color_info.get('has_green') and color_info.get('dominant_color') == 'green':
                    # 如果检测到绿色，很可能是OK
                    if 'OK' in upper or 'O' in upper or 'K' in upper:
                        return 'OK'
                    # 即使文本不清楚，绿色也倾向于OK
                    if not ('NG' in upper or 'N' in upper):
                        return 'OK'
            
            # 标准文本判断
            if 'NG' in upper or upper.startswith('N'):
                return 'NG'
            if 'OK' in upper or 'O' in upper or 'K' in upper:
                return 'OK'
            return text
        
        elif roi_type == 'INTEGER':
            # 提取整数
            match = re.search(r'-?\d+', text)
            if match:
                return match.group(0)
            return text
        
        elif roi_type == 'FLOAT':
            # 提取浮点数并限制小数位数
            match = re.search(r'-?\d+\.?\d*', text)
            if match:
                try:
                    val = float(match.group(0))
                    # 限制3位小数
                    return f"{val:.3f}".rstrip('0').rstrip('.')
                except:
                    pass
            return text
        
        elif roi_type == 'TIME':
            # 提取时间格式
            match = re.search(r'\d{1,2}:\d{2}:\d{2}', text)
            if match:
                return match.group(0)
            return text
        
        return text
    
    def process_single_roi(self, args):
        """并行处理单个ROI"""
        name, x, y, w, h, img, save_dir = args
        H, W = img.shape[:2]
        
        # 1. 边界检查
        if x >= W or y >= H: 
            return name, "NA"
        
        # 2. 裁剪
        x0, y0 = max(0, x - ROI_PAD), max(0, y - ROI_PAD)
        x1, y1 = min(W, x + w + ROI_PAD), min(H, y + h + ROI_PAD)
        crop = img[y0:y1, x0:x1]
        
        if crop.size == 0: 
            return name, "NA"
        
        # 3. 上采样
        if UPSCALE != 1.0:
            crop = cv2.resize(crop, None, fx=UPSCALE, fy=UPSCALE, 
                            interpolation=cv2.INTER_CUBIC)
        
        # 4. 保存裁剪
        crop_filename = save_dir / f"ROI_{name}.jpg"
        cv2.imwrite(str(crop_filename), crop)
        
        # 5. 分析颜色和亮度
        is_valid, color_info = self.analyze_image_colors(crop)
        if not is_valid:
            with print_lock:
                print("D", end="", flush=True)
            return name, "NA"
        
        # 6. OCR识别（带颜色上下文）
        text_val = self.ask_ollama_with_context(crop_filename, name, color_info, attempt=1)
        
        # 7. 保存文本结果
        try:
            with open(save_dir / f"ROI_{name}.txt", "w", encoding="utf-8") as f:
                f.write(text_val)
        except: 
            pass
        
        # 8. 更新median追踪器
        roi_type = get_roi_type(name)
        median_tracker.add_value(name, text_val, roi_type)
        
        # 9. 输出进度
        with print_lock:
            if name in ["51", "52"]:  # 时间戳ROI
                print(f" [{name}: {text_val}] ", end="", flush=True)
            else:
                print(".", end="", flush=True)
        
        return name, text_val
    
    def run_parallel_pipeline(self, img_path, save_dir, relative_parent):
        """并行处理管道"""
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  ❌ Cannot read image: {img_path}")
            return
        
        # 绘制调试地图
        try:
            vis_img = img.copy()
            for name, x, y, w, h in self.rois:
                cv2.rectangle(vis_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(vis_img, name, (x, y-5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            cv2.imwrite(str(save_dir / "_DEBUG_MAP.jpg"), vis_img)
        except: 
            pass
        
        print(f"  --> Processing {len(self.rois)} ROIs with {MAX_WORKERS_3B} workers...")
        start_t = time.time()
        
        collected_results = {}
        
        # 准备并行任务
        tasks = [(name, x, y, w, h, img, save_dir) for name, x, y, w, h in self.rois]
        
        # 并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_3B) as executor:
            results = executor.map(self.process_single_roi, tasks)
            for name, text_val in results:
                collected_results[name] = text_val
        
        duration = time.time() - start_t
        print(f"\n  --> Finished in {duration:.1f}s")
        
        # 保存JSON结果
        try:
            with open(save_dir / "results.json", "w", encoding="utf-8") as f:
                json.dump(collected_results, f, indent=2, ensure_ascii=False)
        except: 
            pass
        
        # 解析元数据
        filename_utc = self.parse_filename_time(img_path.name)
        raw_machine_time = collected_results.get("51", "")
        if not raw_machine_time or raw_machine_time == "NA":
            raw_machine_time = collected_results.get("52", "")
        calc_machine_utc = self.parse_machine_time(raw_machine_time)
        
        # 写入CSV
        for csv_name, id_range in CSV_GROUPS.items():
            self.append_to_summary_csv(
                csv_name, id_range, collected_results,
                img_path.name, filename_utc, raw_machine_time,
                calc_machine_utc, relative_parent
            )
        
        # 打印median统计（每10个图像）
        if self.processed_count % 10 == 0:
            self.print_median_stats()
    
    def print_median_stats(self):
        """打印median统计信息"""
        with print_lock:
            print("\n" + "="*50)
            print("📊 Median Tracker Statistics:")
            for roi_id in sorted(median_tracker.medians.keys()):
                stats = median_tracker.get_stats(roi_id)
                if stats:
                    print(f"  {roi_id}: Median={stats['median']:.2f}, "
                          f"Samples={stats['count']}, "
                          f"Range=[{stats['min']:.2f}, {stats['max']:.2f}]")
            print("="*50)
    
    def append_to_summary_csv(self, csv_name, id_list, results_dict, 
                             filename, file_utc, raw_mach, calc_mach, 
                             relative_parent):
        """追加结果到CSV"""
        target_folder = STAGE_1_OCR / relative_parent / "CSV_Results"
        target_folder.mkdir(parents=True, exist_ok=True)
        csv_path = target_folder / csv_name
        
        header = ["Filename", "File_UTC", "Machine_Text", "Machine_UTC"]
        target_ids = []
        for i in id_list:
            sid = str(i)
            target_ids.append(sid)
            header.append(f"ROI_{sid}")
        
        for extra in ["51", "52"]:
            if extra not in target_ids:
                target_ids.append(extra)
                header.append(f"ROI_{extra}")
        
        row = [filename, file_utc, raw_mach, calc_mach]
        for tid in target_ids:
            val = results_dict.get(tid, "NA").replace("\n", " ").replace(",", ".")
            row.append(val)
        
        with print_lock:
            try:
                file_exists = csv_path.exists()
                with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists: 
                        writer.writerow(header)
                    writer.writerow(row)
            except Exception as e:
                print(f"  ❌ CSV Write Error: {e}")

# ================= 辅助函数 =================
def load_rois(roi_path: Path):
    """加载ROI配置"""
    if not roi_path.exists(): 
        return []
    try:
        with open(roi_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rois = []
        data_list = data if isinstance(data, list) else [data]
        for idx, item in enumerate(data_list):
            name = item.get("name", str(idx))
            rois.append((
                str(name), 
                int(item["x"]), 
                int(item["y"]), 
                int(item["w"]), 
                int(item["h"])
            ))
        return rois
    except Exception as e:
        print(f"❌ Error loading ROI: {e}")
        return []

def main():
    """主函数"""
    # 检查服务器根目录
    if not SERVER_ROOT.exists():
        print(f"❌ Error: SERVER_ROOT does not exist: {SERVER_ROOT}")
        print("   Please create it or update config_pipeline.py")
        return
    
    # 创建必要目录
    create_directories()
    
    # 加载ROI配置
    rois = load_rois(ROI_JSON)
    if not rois:
        print("❌ roi.json missing or invalid")
        return
    
    print("="*60)
    print("🚀 Enhanced OCR Server Started (3B Model)")
    print(f"   Model: {OLLAMA_MODEL_3B}")
    print(f"   Workers: {MAX_WORKERS_3B} (Parallel)")
    print(f"   ROIs: {len(rois)} configured")
    print(f"   Watch Folder: {SOURCE_DIR}")
    print(f"   Output: {STAGE_1_OCR}")
    print("="*60)
    
    handler = EnhancedGPUHandler(rois)
    
    # 1. 扫描现有文件
    print("\n📁 Scanning directory tree...")
    all_files = list(SOURCE_DIR.rglob("*"))
    
    image_files = [
        f for f in all_files
        if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}
        and not f.name.startswith(".")
    ]
    image_files.sort()
    
    total = len(image_files)
    print(f"Found {total} images. Starting batch...\n")
    
    for i, img_path in enumerate(image_files):
        print(f"[{i+1}/{total}]", end=" ")
        try:
            handler.process_new_file(img_path)
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            handler.print_median_stats()
            return
        except Exception as e:
            print(f"\n❌ Error processing {img_path.name}: {e}")
    
    print("\n✅ Batch done. Monitoring for NEW files...")
    handler.print_median_stats()
    
    # 2. 监控新文件
    observer = Observer()
    observer.schedule(handler, str(SOURCE_DIR), recursive=True)
    observer.start()
    
    try:
        while True: 
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Server stopped.")
        handler.print_median_stats()
    observer.join()

if __name__ == "__main__":
    main()

