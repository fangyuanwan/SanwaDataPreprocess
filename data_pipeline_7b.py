"""
7B模型验证管道 - 高精度验证和冗余消除
7B Model Verification Pipeline - High Precision Verification and Redundancy Removal

流程 Pipeline:
1. 标记数据状态（时间冻结、数据冗余）
2. 7B模型验证冗余不匹配
3. 应用7B修正
4. 重新标记
5. 消除冗余行
6. 生成最终数据集

输入 Input: Stage 3 - 3B修正后的数据
输出 Output: Stage 6 - 最终清洁数据集
"""

import pandas as pd
import numpy as np
import os
import sys
import json
import glob
import shutil
import re
import ollama
from pathlib import Path
from datetime import datetime
import threading

# 导入配置
from config_pipeline import *

print_lock = threading.Lock()

# ================= 阶段4: 数据标记 =================
class Stage4_DataLabeling:
    """阶段4: 标记数据状态（时间、冗余）"""
    
    def __init__(self, input_dir, output_dir, crops_base):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.crops_base = Path(crops_base)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def parse_pc_filename_time(self, filename):
        """从文件名提取时间戳"""
        try:
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}\.\d{2}\.\d{2})', str(filename))
            if match:
                clean_str = match.group(1).replace('.', ':')
                return datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None
        return None
    
    def get_positional_data(self, row, columns_list):
        """获取用于比较的位置数据"""
        start_idx = 4
        if 'ROI_51' in columns_list:
            end_idx = columns_list.index('ROI_51')
        elif 'ROI_52' in columns_list:
            end_idx = columns_list.index('ROI_52')
        else:
            end_idx = len(columns_list)
        
        if start_idx >= end_idx:
            return [], []
        
        cols_to_check = columns_list[start_idx:end_idx]
        values = [str(row.get(col, '')).strip() for col in cols_to_check]
        return values, cols_to_check
    
    def calculate_similarity(self, list_a, list_b):
        """计算相似度"""
        if not list_a or not list_b or len(list_a) != len(list_b):
            return 0.0
        matches = sum(1 for a, b in zip(list_a, list_b) if a == b)
        return matches / len(list_a)
    
    def get_config_for_file(self, df):
        """获取文件配置"""
        for config in ROI_CONFIGS:
            if config['Trigger_Col'] in df.columns:
                return config
        return None
    
    def copy_crop_for_review(self, csv_base, filename, roi_id, dest_folder):
        """复制裁剪图像"""
        try:
            folder_name = os.path.splitext(filename)[0]
            
            potential_paths = [
                self.crops_base / csv_base / folder_name / f"{roi_id}.jpg",
                self.crops_base / csv_base / folder_name / f"{roi_id}.png",
                self.crops_base / folder_name / f"{roi_id}.jpg",
                self.crops_base / folder_name / f"{roi_id}.png",
            ]
            
            for p in potential_paths:
                if p.exists():
                    target_folder = dest_folder / folder_name
                    target_folder.mkdir(parents=True, exist_ok=True)
                    shutil.copy(p, target_folder / p.name)
                    return True
            return False
        except:
            return False
    
    def process_single_csv(self, csv_path):
        """处理单个CSV并标记"""
        filename = csv_path.name
        base_name = csv_path.stem.replace("_3B_Corrected", "")
        
        # 获取自适应阈值
        similarity_threshold = get_similarity_threshold(filename)
        
        print(f"\n🏷️  Labeling: {filename} (Threshold: {similarity_threshold})")
        
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return
        
        config = self.get_config_for_file(df)
        if not config:
            print(f"  ⚠️  Skipped: Unknown format")
            return
        
        if 'Filename' in df.columns:
            df.sort_values(by='Filename', inplace=True)
        
        df_clean = df.copy()
        
        # 初始化新列
        df_clean['Time_Status'] = 'Unknown'
        df_clean['Data_Redundancy'] = 'Unknown'
        df_clean['Matched_File'] = ''
        df_clean['Duration_Since_Change'] = 0.0
        
        redundancy_mismatch_records = []
        
        # 转换为记录列表
        rows_list = df_clean.to_dict('records')
        columns_list = df_clean.columns.tolist()
        all_row_data = [self.get_positional_data(row, columns_list) for row in rows_list]
        
        prev_plc_time_str = None
        state_start_pc_time = None
        
        print(f"  📊 Analyzing {len(rows_list)} rows for time/redundancy patterns...")
        
        for i in range(len(rows_list)):
            curr_row = rows_list[i]
            curr_idx = df_clean.index[i]
            curr_filename = curr_row.get('Filename', '')
            
            curr_pc_obj = self.parse_pc_filename_time(curr_filename)
            curr_plc_str = str(curr_row.get('ROI_52', '')).strip()
            
            curr_vals, curr_cols = all_row_data[i]
            prev_vals, _ = all_row_data[i-1] if i > 0 else ([], [])
            next_vals, _ = all_row_data[i+1] if i < len(rows_list)-1 else ([], [])
            
            prev_filename = df_clean.at[df_clean.index[i-1], 'Filename'] if i > 0 else ""
            next_filename = df_clean.at[df_clean.index[i+1], 'Filename'] if i < len(rows_list)-1 else ""
            
            # 时间状态逻辑
            time_status = "New Time State"
            duration = 0.0
            
            if i == 0 or curr_pc_obj is None:
                time_status = "New Time State (Start)"
                state_start_pc_time = curr_pc_obj
            else:
                if curr_plc_str == prev_plc_time_str:
                    time_status = "Time Static"
                    if state_start_pc_time and curr_pc_obj:
                        duration = (curr_pc_obj - state_start_pc_time).total_seconds()
                    if duration > FROZEN_THRESHOLD_SECONDS:
                        time_status = "Time Frozen (>10s)"
                else:
                    state_start_pc_time = curr_pc_obj
            prev_plc_time_str = curr_plc_str
            
            # 模糊冗余逻辑
            is_redundant_prev = False
            is_redundant_next = False
            
            similarity_prev = self.calculate_similarity(curr_vals, prev_vals)
            if i > 0 and similarity_prev >= similarity_threshold:
                is_redundant_prev = True
                for k in range(len(curr_vals)):
                    if curr_vals[k] != prev_vals[k]:
                        redundancy_mismatch_records.append({
                            'Filename_Current': curr_filename,
                            'Filename_Compared': prev_filename,
                            'ROI_ID': curr_cols[k],
                            'Value_Current': curr_vals[k],
                            'Value_Compared': prev_vals[k],
                            'Similarity_Score': round(similarity_prev, 2),
                            'Reason': 'Redundant Row Value Mismatch'
                        })
            
            similarity_next = self.calculate_similarity(curr_vals, next_vals)
            if i < len(rows_list)-1 and similarity_next >= similarity_threshold:
                is_redundant_next = True
            
            data_redundancy_list = []
            matched_files_list = []
            if not is_redundant_prev and not is_redundant_next:
                data_redundancy = "Unique"
            else:
                if is_redundant_prev:
                    data_redundancy_list.append(f"Redundant Prev ({int(similarity_prev*100)}%)")
                    matched_files_list.append(f"Prev: {prev_filename}")
                if is_redundant_next:
                    data_redundancy_list.append(f"Redundant Next ({int(similarity_next*100)}%)")
                    matched_files_list.append(f"Next: {next_filename}")
                data_redundancy = " & ".join(data_redundancy_list)
            
            df_clean.at[curr_idx, 'Time_Status'] = time_status
            df_clean.at[curr_idx, 'Data_Redundancy'] = data_redundancy
            df_clean.at[curr_idx, 'Matched_File'] = " | ".join(matched_files_list)
            df_clean.at[curr_idx, 'Duration_Since_Change'] = round(duration, 2)
        
        # 保存结果
        df_clean.to_csv(self.output_dir / f"{base_name}_Labeled.csv", index=False)
        
        # 保存冗余不匹配日志
        if redundancy_mismatch_records:
            df_mis = pd.DataFrame(redundancy_mismatch_records).drop_duplicates()
            df_mis.to_csv(self.output_dir / f"{base_name}_Redundancy_Mismatch_Log.csv", index=False)
            
            mis_dest = REDUNDANCY_CROPS_BASE / base_name
            mis_dest.mkdir(parents=True, exist_ok=True)
            
            count = sum(1 for _, r in df_mis.iterrows() 
                       if self.copy_crop_for_review(base_name, r['Filename_Current'], 
                                                   r['ROI_ID'], mis_dest))
            
            print(f"  ⚠️  Redundancy Mismatches: {len(df_mis)} (Copied {count} images)")
        
        print(f"  ✅ Labeled: {base_name}_Labeled.csv")
    
    def run(self):
        """运行标记流程"""
        print("\n" + "="*60)
        print("STAGE 4: Data Labeling (Time/Redundancy Analysis)")
        print("="*60)
        
        csv_files = list(self.input_dir.glob("*_3B_Corrected.csv"))
        
        if not csv_files:
            print("❌ No 3B corrected files found")
            return
        
        print(f"Found {len(csv_files)} files\n")
        
        for csv_file in csv_files:
            self.process_single_csv(csv_file)
        
        print("\n✅ Stage 4 Complete")

# ================= 阶段5: 7B验证 =================
class Stage5_7BVerification:
    """阶段5: 使用7B模型验证冗余不匹配"""
    
    def __init__(self, labeled_dir, output_dir, crops_base):
        self.labeled_dir = Path(labeled_dir)
        self.output_dir = Path(output_dir)
        self.crops_base = Path(crops_base)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def calculate_roi_medians(self, csv_path):
        """
        从CSV计算每个ROI的median值
        返回: {roi_id: median_value}
        """
        try:
            df = pd.read_csv(csv_path)
            roi_medians = {}
            
            print(f"  📊 Calculating medians from {len(df)} rows...")
            
            for col in df.columns:
                if not col.startswith('ROI_'):
                    continue
                
                roi_type = get_roi_type(col)
                
                # 只对数值类型计算median
                if roi_type in ['INTEGER', 'FLOAT']:
                    try:
                        # 转换为数值，忽略错误
                        vals = pd.to_numeric(df[col], errors='coerce').dropna()
                        # 过滤掉0值（可能是缺陷）
                        vals = vals[vals > 0]
                        
                        if len(vals) >= 5:  # 至少5个有效样本
                            roi_medians[col] = vals.median()
                            print(f"    ✓ {col}: Median={roi_medians[col]:.3f} (from {len(vals)} samples)")
                    except:
                        pass
                
                elif roi_type == 'STATUS':
                    # 对于STATUS，找出最常见的值
                    try:
                        value_counts = df[col].value_counts()
                        if not value_counts.empty:
                            roi_medians[col] = value_counts.index[0]  # 最常见的值
                            print(f"    ✓ {col}: Most common={roi_medians[col]}")
                    except:
                        pass
            
            print(f"  📊 Calculated medians for {len(roi_medians)} ROI fields")
            return roi_medians
            
        except Exception as e:
            print(f"  ⚠️  Error calculating medians: {e}")
            return {}
    
    def get_prompt_7b_enhanced(self, roi_id, current_val, compared_val, median_val,
                              prev_filename='', curr_filename=''):
        """
        生成增强的7B验证prompt（使用mismatch类型，支持双图像比较）
        """
        return get_prompt(
            roi_id=roi_id,
            prompt_type='mismatch',
            median_value=median_val,
            compared_value=compared_val,
            current_value=current_val,
            prev_filename=prev_filename,
            curr_filename=curr_filename
        )
    
    def run_7b_inference_dual(self, image_path_prev, image_path_curr, prompt):
        """
        使用7B模型推理（双图像输入）
        """
        try:
            # 准备双图像消息
            response = ollama.chat(
                model=OLLAMA_MODEL_7B,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [str(image_path_prev), str(image_path_curr)]  # 发送两张图像
                }],
                options={'temperature': 0.1, 'num_predict': 30}
            )
            
            text = response['message']['content']
            text = re.sub(r'<[^>]+>', '', text).replace('```', '').replace('`', '').strip()
            text = text.split('\n')[0].strip()
            
            return text if text else "ERROR"
            
        except Exception as e:
            print(f"  [7B Dual Error] {e}")
            return "ERROR"
    
    def run_7b_inference(self, image_path, prompt):
        """使用7B模型推理"""
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL_7B,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [str(image_path)]
                }],
                options={'temperature': 0.1, 'num_predict': 30}
            )
            
            text = response['message']['content']
            text = re.sub(r'<[^>]+>', '', text).replace('```', '').replace('`', '').strip()
            text = text.split('\n')[0].strip()
            
            return text if text else "ERROR"
            
        except Exception as e:
            print(f"  [7B Error] {e}")
            return "ERROR"
    
    def find_crop_image(self, csv_base, filename, roi_id):
        """查找裁剪图像"""
        folder_name = os.path.splitext(filename)[0]
        
        potential_paths = [
            self.crops_base / csv_base / folder_name / f"{roi_id}.jpg",
            self.crops_base / csv_base / folder_name / f"{roi_id}.png",
            self.crops_base / folder_name / f"{roi_id}.jpg",
            self.crops_base / folder_name / f"{roi_id}.png",
        ]
        
        for p in potential_paths:
            if p.exists():
                return p
        return None
    
    def process_mismatch_log(self, log_path):
        """处理冗余不匹配日志（增强版：带median计算和双图像比较）"""
        filename = log_path.name
        csv_base = filename.replace("_Redundancy_Mismatch_Log.csv", "")
        
        print(f"\n🔍 Verifying with 7B (Dual Image Comparison): {filename}")
        
        try:
            df = pd.read_csv(log_path)
        except:
            print(f"  ❌ Could not read CSV")
            return
        
        if df.empty:
            print(f"  ✅ Log is empty")
            return
        
        # 加载对应的labeled CSV来计算median
        labeled_csv = self.labeled_dir / f"{csv_base}_Labeled.csv"
        roi_medians = {}
        
        if labeled_csv.exists():
            print(f"  📊 Calculating median values from {labeled_csv.name}...")
            roi_medians = self.calculate_roi_medians(labeled_csv)
        else:
            print(f"  ⚠️  Labeled CSV not found, proceeding without median context")
        
        # 添加新列
        df['AI_7B_Read'] = ""
        df['Verdict'] = ""
        df['Image_Source_Prev'] = ""
        df['Image_Source_Curr'] = ""
        df['Median_Context'] = ""
        df['Comparison_Mode'] = ""
        
        for idx, row in df.iterrows():
            roi_id = str(row['ROI_ID'])
            roi_type = get_roi_type(roi_id)
            current_filename = str(row['Filename_Current'])
            compared_filename = str(row['Filename_Compared'])
            
            # 查找两张图像（prev和current）
            img_path_prev = self.find_crop_image(csv_base, compared_filename, roi_id)
            img_path_curr = self.find_crop_image(csv_base, current_filename, roi_id)
            
            # 检查图像是否都找到
            if not img_path_prev or not img_path_curr:
                df.at[idx, 'AI_7B_Read'] = "Image Not Found"
                df.at[idx, 'Image_Source_Prev'] = str(img_path_prev) if img_path_prev else "Missing"
                df.at[idx, 'Image_Source_Curr'] = str(img_path_curr) if img_path_curr else "Missing"
                print(f"  [{idx+1}/{len(df)}] {roi_id}: ❌ Image(s) missing")
                continue
            
            # 获取median值
            median_val = roi_medians.get(roi_id, None)
            df.at[idx, 'Median_Context'] = str(median_val) if median_val is not None else "N/A"
            
            # 获取当前值和比较值
            val_curr = row['Value_Current']
            val_prev = row['Value_Compared']
            
            # 只对INTEGER和FLOAT使用双图像比较
            if roi_type in ['INTEGER', 'FLOAT']:
                # 生成包含双图像信息的prompt
                prompt = self.get_prompt_7b_enhanced(
                    roi_id, val_curr, val_prev, median_val,
                    prev_filename=compared_filename,
                    curr_filename=current_filename
                )
                
                # 7B双图像推理
                ai_result = self.run_7b_inference_dual(img_path_prev, img_path_curr, prompt)
                df.at[idx, 'Comparison_Mode'] = "Dual Image"
            else:
                # STATUS和TIME只用单图像（current）
                prompt = self.get_prompt_7b_enhanced(
                    roi_id, val_curr, val_prev, median_val,
                    prev_filename=compared_filename,
                    curr_filename=current_filename
                )
                ai_result = self.run_7b_inference(img_path_curr, prompt)
                df.at[idx, 'Comparison_Mode'] = "Single Image"
            
            # 显示详细信息
            median_str = f"Median={median_val:.3f}" if isinstance(median_val, (int, float)) else f"Mode={median_val}"
            mode_icon = "🔬" if roi_type in ['INTEGER', 'FLOAT'] else "📷"
            print(f"  [{idx+1}/{len(df)}] {mode_icon} {roi_id}: Prev={val_prev} | Curr={val_curr} | {median_str} | 7B={ai_result}")
            
            # 保存结果
            df.at[idx, 'AI_7B_Read'] = ai_result
            df.at[idx, 'Image_Source_Prev'] = str(img_path_prev)
            df.at[idx, 'Image_Source_Curr'] = str(img_path_curr)
            
            # 判定（增强版：考虑median）
            ai_clean = str(ai_result).strip().lower()
            prev_clean = str(val_prev).strip().lower()
            curr_clean = str(val_curr).strip().lower()
            
            if ai_clean == prev_clean:
                df.at[idx, 'Verdict'] = "Confirmed Redundant (OCR Error)"
            elif ai_clean == curr_clean:
                df.at[idx, 'Verdict'] = "Genuine Change (OCR Correct)"
            else:
                # 如果7B给出新值，检查是否接近median
                verdict = "New Value (7B Disagrees)"
                if median_val is not None and roi_type in ['INTEGER', 'FLOAT']:
                    try:
                        ai_num = float(ai_clean)
                        median_num = float(median_val)
                        if abs(ai_num - median_num) / median_num < 0.1:  # 10%以内
                            verdict += " - Close to Median"
                        else:
                            # 检查哪个读数更接近median
                            try:
                                prev_diff = abs(float(prev_clean) - median_num) / median_num
                                curr_diff = abs(float(curr_clean) - median_num) / median_num
                                if prev_diff < curr_diff:
                                    verdict += f" - Prev closer to median"
                                else:
                                    verdict += f" - Curr closer to median"
                            except:
                                pass
                    except:
                        pass
                df.at[idx, 'Verdict'] = verdict
        
        # 保存
        out_name = filename.replace(".csv", "_AI_7B_Verified.csv")
        df.to_csv(self.output_dir / out_name, index=False)
        
        # 统计
        dual_count = len(df[df['Comparison_Mode'] == 'Dual Image'])
        single_count = len(df[df['Comparison_Mode'] == 'Single Image'])
        print(f"  ✅ Saved: {out_name}")
        print(f"  📊 Comparison: {dual_count} dual-image, {single_count} single-image")
    
    def run(self):
        """运行7B验证流程"""
        print("\n" + "="*60)
        print("STAGE 5: 7B Model Verification")
        print("="*60)
        
        mismatch_logs = list(self.labeled_dir.glob("*_Redundancy_Mismatch_Log.csv"))
        
        if not mismatch_logs:
            print("✅ No mismatch logs found - data is consistent!")
            return
        
        print(f"Found {len(mismatch_logs)} mismatch logs\n")
        
        for log_path in mismatch_logs:
            self.process_mismatch_log(log_path)
        
        print("\n✅ Stage 5 Complete")

# ================= 阶段6: 应用7B修正并消除冗余 =================
class Stage6_FinalConsolidation:
    """阶段6: 应用7B修正并消除冗余行，生成最终数据集"""
    
    def __init__(self, labeled_dir, verified_logs_dir, output_dir):
        self.labeled_dir = Path(labeled_dir)
        self.verified_logs_dir = Path(verified_logs_dir)
        self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def apply_7b_corrections(self, labeled_csv_path, verified_log_path):
        """应用7B修正"""
        print(f"\n🔧 Applying 7B corrections: {labeled_csv_path.name}")
        
        try:
            df_main = pd.read_csv(labeled_csv_path)
            df_log = pd.read_csv(verified_log_path)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
        
        if df_log.empty:
            return df_main
        
        df_main['Filename'] = df_main['Filename'].astype(str)
        
        corrections = []
        for _, row in df_log.iterrows():
            ai_val = str(row.get('AI_7B_Read', '')).strip()
            
            if ai_val in ["", "nan", "Image Not Found", "ERROR"]:
                continue
            
            corrections.append({
                'curr': row['Filename_Current'],
                'comp': row['Filename_Compared'],
                'roi': row['ROI_ID'],
                'val': ai_val
            })
        
        patch_count = 0
        for item in corrections:
            target_roi = item['roi']
            new_val = item['val']
            
            if target_roi not in df_main.columns:
                continue
            
            # 更新当前行和比较行
            mask_curr = df_main['Filename'] == item['curr']
            if mask_curr.any():
                df_main.loc[mask_curr, target_roi] = new_val
                patch_count += 1
            
            mask_comp = df_main['Filename'] == item['comp']
            if mask_comp.any():
                df_main.loc[mask_comp, target_roi] = new_val
                patch_count += 1
        
        print(f"  ✅ Patched {patch_count} cells")
        return df_main
    
    def check_redundancy_pair(self, curr_row, next_row):
        """检查是否为冗余对"""
        curr_status = str(curr_row.get('Data_Redundancy', ''))
        next_status = str(next_row.get('Data_Redundancy', ''))
        
        has_next = "Redundant Next" in curr_status
        has_prev = "Redundant Prev" in next_status or "Redundant Previous" in next_status
        
        return has_next and has_prev
    
    def parse_pc_filename_time(self, filename):
        """解析文件名时间"""
        try:
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}\.\d{2}\.\d{2})', str(filename))
            if match:
                clean_str = match.group(1).replace('.', ':')
                return datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None
        return None
    
    def consolidate_redundancy(self, df):
        """消除冗余行"""
        print(f"  🗜️  Consolidating redundancy...")
        
        df.sort_values(by='Filename', inplace=True)
        rows = df.to_dict('records')
        total_rows = len(rows)
        
        kept_rows = []
        deletion_log = []
        
        i = 0
        while i < total_rows:
            curr_row = rows[i]
            
            if i < total_rows - 1:
                next_row = rows[i+1]
                
                if self.check_redundancy_pair(curr_row, next_row):
                    kept_rows.append(curr_row)
                    deletion_log.append({
                        'Deleted_Filename': next_row['Filename'],
                        'Reason': "Pairwise Compression (Matches Previous)",
                        'Original_Status': next_row.get('Data_Redundancy')
                    })
                    i += 2
                    continue
            
            kept_rows.append(curr_row)
            i += 1
        
        # 计算真实时间间隔
        for k in range(len(kept_rows)):
            curr_item = kept_rows[k]
            curr_time = self.parse_pc_filename_time(curr_item['Filename'])
            
            step_duration = 0.0
            
            if k > 0:
                prev_item = kept_rows[k-1]
                prev_time = self.parse_pc_filename_time(prev_item['Filename'])
                
                if curr_time and prev_time:
                    step_duration = (curr_time - prev_time).total_seconds()
            
            curr_item['Real_Freeze_Duration_Sec'] = round(step_duration, 2)
            
            if "Redundant" in str(curr_item.get('Data_Redundancy', '')):
                curr_item['Data_Redundancy'] = f"Redundant Pair (Kept 1st) | Gap: {step_duration}s"
        
        df_final = pd.DataFrame(kept_rows)
        
        print(f"  ✅ Compression: {total_rows} → {len(df_final)} rows (Removed {len(deletion_log)})")
        
        return df_final, deletion_log
    
    def process_single_file(self, labeled_csv_path):
        """处理单个文件"""
        base_name = labeled_csv_path.stem.replace("_Labeled", "")
        
        print(f"\n📦 Finalizing: {labeled_csv_path.name}")
        
        # 查找对应的7B验证日志
        verified_log = self.verified_logs_dir / f"{base_name}_Redundancy_Mismatch_Log_AI_7B_Verified.csv"
        
        df_corrected = None
        if verified_log.exists():
            df_corrected = self.apply_7b_corrections(labeled_csv_path, verified_log)
        else:
            df_corrected = pd.read_csv(labeled_csv_path)
            print(f"  ℹ️  No 7B corrections needed")
        
        if df_corrected is None:
            return
        
        # 消除冗余
        df_final, deletion_log = self.consolidate_redundancy(df_corrected)
        
        # 保存最终数据集
        out_name = f"{base_name}_Final.csv"
        df_final.to_csv(self.output_dir / out_name, index=False)
        print(f"  💾 Saved: {out_name}")
        
        # 保存删除日志
        if deletion_log:
            log_name = f"{base_name}_Deletion_Log.csv"
            pd.DataFrame(deletion_log).to_csv(self.output_dir / log_name, index=False)
    
    def run(self):
        """运行最终整合流程"""
        print("\n" + "="*60)
        print("STAGE 6: Final Consolidation (Apply 7B + Remove Redundancy)")
        print("="*60)
        
        labeled_files = list(self.labeled_dir.glob("*_Labeled.csv"))
        
        if not labeled_files:
            print("❌ No labeled files found")
            return
        
        print(f"Found {len(labeled_files)} labeled files\n")
        
        for csv_file in labeled_files:
            self.process_single_file(csv_file)
        
        print("\n✅ Stage 6 Complete")

# ================= 主流程 =================
def main():
    """7B管道主流程"""
    print("\n" + "="*80)
    print("🤖 7B MODEL VERIFICATION PIPELINE")
    print("="*80)
    
    # 阶段4: 数据标记
    stage4 = Stage4_DataLabeling(
        input_dir=STAGE_3_3B_CORRECTED,
        output_dir=STAGE_4_LABELED,
        crops_base=STAGE_1_OCR / "debug_crops"
    )
    stage4.run()
    
    # 阶段5: 7B验证
    stage5 = Stage5_7BVerification(
        labeled_dir=STAGE_4_LABELED,
        output_dir=STAGE_5_7B_VERIFIED,
        crops_base=STAGE_1_OCR / "debug_crops"
    )
    stage5.run()
    
    # 阶段6: 最终整合
    stage6 = Stage6_FinalConsolidation(
        labeled_dir=STAGE_4_LABELED,
        verified_logs_dir=STAGE_5_7B_VERIFIED,
        output_dir=STAGE_6_FINAL
    )
    stage6.run()
    
    print("\n" + "="*80)
    print("🎉 7B PIPELINE COMPLETE")
    print(f"📂 Final Clean Dataset: {STAGE_6_FINAL}")
    print("="*80)

if __name__ == "__main__":
    main()

