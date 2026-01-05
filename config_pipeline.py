"""
数据处理管道的统一配置文件
Unified Configuration for Data Processing Pipeline
"""
from pathlib import Path

# ================= 目录配置 / Directory Configuration =================
# 服务器根目录 / Server Root Directory
SERVER_ROOT = Path("/home/ubuntu/sanwa_project")

# 输入输出目录 / Input/Output Directories
SOURCE_DIR = SERVER_ROOT / "input_images"
OUTPUT_BASE = SERVER_ROOT / "pipeline_output"

# 各阶段输出目录 / Stage Output Directories
STAGE_1_OCR = OUTPUT_BASE / "stage1_ocr_results"
STAGE_2_CLEANED = OUTPUT_BASE / "stage2_cleaned_data"
STAGE_3_3B_CORRECTED = OUTPUT_BASE / "stage3_3b_corrected"
STAGE_4_LABELED = OUTPUT_BASE / "stage4_labeled"
STAGE_5_7B_VERIFIED = OUTPUT_BASE / "stage5_7b_verified"
STAGE_6_FINAL = OUTPUT_BASE / "stage6_final_dataset"

# 调试和检查目录 / Debug and Review Directories
DEBUG_CROPS_BASE = OUTPUT_BASE / "debug_crops"
ABNORMAL_CROPS_BASE = OUTPUT_BASE / "abnormal_crops_review"
REDUNDANCY_CROPS_BASE = OUTPUT_BASE / "redundancy_crops_review"

# ================= 模型配置 / Model Configuration =================
OLLAMA_MODEL_3B = "qwen2.5vl:3b"
OLLAMA_MODEL_7B = "qwen2.5vl:7b"

# GPU并行处理配置 / GPU Parallel Processing
# 配置说明：您有 4x V100 GPUs (32GB each)
# 
# V100性能参考：
# - 3B模型：~2-3GB显存/实例，每块GPU可同时运行8-10个实例
# - 7B模型：~6-8GB显存/实例，每块GPU可同时运行3-4个实例
#
# 推荐配置（4块V100）：
MAX_WORKERS_3B = 16  # 4 GPUs * 4 workers = 16 (保守配置)
                     # 可以尝试 20-24 如果显存充足
MAX_WORKERS_7B = 8   # 4 GPUs * 2 workers = 8 (保守配置)
                     # 可以尝试 12 如果显存充足

# 性能调优建议：
# - 监控GPU使用率：nvidia-smi -l 1
# - 如果GPU利用率 < 80%，可以增加workers
# - 如果出现OOM错误，减少workers
# - 3B模型处理速度快，可以设置更多workers
# - 7B模型显存需求大，workers数量要保守

# ================= ROI配置 / ROI Configuration =================
ROI_JSON = Path("roi.json")
ROI_PAD = 2
UPSCALE = 2.0
DARKNESS_THRESHOLD = 15

# ROI数据类型映射 / ROI Data Type Mapping
ROI_CONFIGS = [
    {
        'Trigger_Col': 'ROI_12',
        'CSV_Name': 'cam 6 snap1 Latchresult.csv',
        'Columns': {
            'ROI_12': 'STATUS', 'ROI_14': 'STATUS', 'ROI_15': 'STATUS', 
            'ROI_17': 'STATUS', 'ROI_19': 'STATUS',
            'ROI_13': 'INTEGER', 'ROI_16': 'FLOAT', 'ROI_18': 'FLOAT', 
            'ROI_52': 'TIME'
        }
    },
    {
        'Trigger_Col': 'ROI_20',
        'CSV_Name': 'cam 6 snap2 nozzleresult.csv',
        'Columns': {
            'ROI_20': 'STATUS', 'ROI_22': 'STATUS', 'ROI_24': 'STATUS', 
            'ROI_25': 'STATUS', 'ROI_26': 'STATUS', 'ROI_27': 'STATUS', 
            'ROI_28': 'STATUS', 'ROI_29': 'STATUS', 'ROI_30': 'STATUS',
            'ROI_21': 'INTEGER', 'ROI_23': 'FLOAT', 
            'ROI_52': 'TIME'
        }
    },
    {
        'Trigger_Col': 'ROI_1',
        'CSV_Name': 'CslotCam4result.csv',
        'Columns': {
            'ROI_1': 'STATUS', 'ROI_3': 'STATUS', 'ROI_5': 'STATUS', 
            'ROI_7': 'STATUS', 'ROI_9': 'STATUS', 'ROI_10': 'STATUS', 
            'ROI_11': 'STATUS',
            'ROI_2': 'INTEGER', 'ROI_4': 'FLOAT', 'ROI_6': 'FLOAT', 
            'ROI_8': 'FLOAT', 
            'ROI_52': 'TIME'
        }
    },
    {
        'Trigger_Col': 'ROI_31',
        'CSV_Name': 'terminal result.csv',
        'Columns': {
            'ROI_31': 'STATUS', 'ROI_33': 'STATUS', 'ROI_34': 'STATUS', 
            'ROI_36': 'STATUS', 'ROI_38': 'STATUS', 'ROI_40': 'STATUS', 
            'ROI_42': 'STATUS', 'ROI_44': 'STATUS', 'ROI_46': 'STATUS', 
            'ROI_48': 'STATUS', 'ROI_50': 'STATUS',
            'ROI_32': 'INTEGER', 'ROI_35': 'INTEGER', 'ROI_37': 'INTEGER', 
            'ROI_39': 'INTEGER', 'ROI_41': 'INTEGER', 'ROI_43': 'INTEGER', 
            'ROI_45': 'INTEGER', 'ROI_47': 'INTEGER', 'ROI_49': 'INTEGER',
            'ROI_52': 'TIME'
        }
    }
]

# CSV分组配置 / CSV Grouping Configuration
CSV_GROUPS = {
    "CslotCam4result.csv": list(range(1, 12)),
    "cam 6 snap1 Latchresult.csv": list(range(12, 20)),
    "cam 6 snap2 nozzleresult.csv": list(range(20, 31)),
    "terminal result.csv": list(range(31, 51))
}

# 扁平化ROI类型映射 / Flatten ROI Type Map
ROI_TYPE_MAP = {}
for cfg in ROI_CONFIGS:
    ROI_TYPE_MAP.update(cfg['Columns'])

# ================= 数据验证配置 / Data Validation Configuration =================
MAX_DECIMALS = 3
OUTLIER_THRESHOLD = 5.0
FROZEN_THRESHOLD_SECONDS = 10.0

# 自适应阈值配置（针对不同数据集）/ Adaptive Threshold Configuration
SIMILARITY_THRESHOLDS = {
    "CslotCam4result.csv": 0.85,          # C-slot较敏感
    "cam 6 snap1 Latchresult.csv": 0.80,  # Latch默认
    "cam 6 snap2 nozzleresult.csv": 0.95, # Nozzle默认
    "terminal result.csv": 0.90           # Terminal数据点多，阈值更高
}

# 默认相似度阈值 / Default Similarity Threshold
DEFAULT_SIMILARITY_THRESHOLD = 0.80

# ================= Prompt模板 / Prompt Templates =================

# 通用噪声过滤规则（应用于所有prompt）
NOISE_FILTER_RULES = """
⚠️ NOISE FILTERING RULES (CRITICAL):
1. IGNORE half-cut numbers at edges (only partial digits visible)
2. IGNORE text with different colored background that's cut off
3. IGNORE background patterns or decorative elements
4. ONLY read complete, fully visible numbers in the main display area
5. If a digit is only 50% visible or less → DO NOT guess, skip it
6. Focus on the primary number display, not peripheral text
"""

PROMPTS = {
    'STATUS': {
        'initial': (
            "Task: Classify the status indicator in this image.\n"
            "Rules:\n"
            "1. Output ONLY 'OK' or 'NG' (nothing else).\n"
            "2. Look for text patterns:\n"
            "   - 'OK', 'O', 'K', '0' (zero) → Output: OK\n"
            "   - 'NG', 'N', 'G' → Output: NG\n"
            "3. If image is blank or unreadable → Output: NG\n"
            "4. NO markdown, NO explanations.\n"
            "\n" + NOISE_FILTER_RULES
        ),
        'correction': (
            "Task: Re-verify the status indicator.\n"
            "Context: OCR previously read '{ocr_value}', but validation failed.\n"
            "Expected median nearby: {median_context}\n"
            "Rules:\n"
            "1. Look VERY carefully at the image\n"
            "2. Output ONLY 'OK' or 'NG'\n"
            "3. Trust what you SEE, not the previous OCR result"
        )
    },
    'INTEGER': {
        'initial': (
            "Task: Extract the integer number from this digital display.\n"
            "Rules:\n"
            "1. Output ONLY the integer (no decimals, no units)\n"
            "2. If negative, include the '-' sign\n"
            "3. If blank or error → Output: 0\n"
            "4. Remove any non-digit characters\n"
            "5. NO markdown formatting\n"
            "\n" + NOISE_FILTER_RULES
        ),
        'correction': (
            "Task: Re-read this integer value with high precision.\n"
            "Context: OCR read '{ocr_value}', expected around {median_context}\n"
            "Common errors to check:\n"
            "- Missing digits\n"
            "- Extra digits\n"
            "- Sign errors\n"
            "Output ONLY the correct integer.\n"
            "\n" + NOISE_FILTER_RULES
        )
    },
    'FLOAT': {
        'initial': (
            "Task: Extract the floating-point number from this sensor reading.\n"
            "Rules:\n"
            "1. Output ONLY the number (include decimal point)\n"
            "2. Maximum 3 decimal places (e.g., 9.181 not 9.18181)\n"
            "3. If value is 0 or blank → Output: 0\n"
            "4. Common patterns:\n"
            "   - '1.88' NOT '188' (watch for decimal point)\n"
            "   - Negative values: include '-' sign\n"
            "5. NO markdown, NO units\n"
            "\n" + NOISE_FILTER_RULES
        ),
        'correction': (
            "Task: Re-extract floating-point number with EXTREME precision.\n"
            "Context: OCR read '{ocr_value}', typical value is around {median_context}\n"
            "CRITICAL CHECKS:\n"
            "1. Decimal point position (e.g., '188' should be '1.88'?)\n"
            "2. Is there a decimal point visible?\n"
            "3. If display shows '0' or is blank → Output: 0 (defect)\n"
            "4. Truncate to 3 decimals max\n"
            "Output format: X.XXX\n"
            "\n" + NOISE_FILTER_RULES
        )
    },
    'TIME': {
        'initial': (
            "Task: Read the timestamp from this display.\n"
            "Rules:\n"
            "1. Output ONLY in format HH:MM:SS\n"
            "2. Use 24-hour format\n"
            "3. Include leading zeros (e.g., 09:05:03)\n"
            "4. Remove any trailing text or dates\n"
            "5. NO markdown"
        ),
        'correction': (
            "Task: Re-read timestamp carefully.\n"
            "Context: Previous read was '{ocr_value}'\n"
            "Check for:\n"
            "- Correct colon positions\n"
            "- All digits present\n"
            "- No extra characters\n"
            "Output: HH:MM:SS"
        ),
        'mismatch': (
            "Task: Resolve timestamp dispute with HIGH precision.\n"
            "Conflict situation:\n"
            "  - Previous scan read: '{compared_value}'\n"
            "  - Current scan read: '{current_value}'\n"
            "  - These should be identical (redundant data)\n"
            "\n"
            "Your mission:\n"
            "1. Look at this image VERY carefully\n"
            "2. Read the timestamp exactly as shown\n"
            "3. Format: HH:MM:SS (24-hour format)\n"
            "4. If display is blank/dark → Output: NA\n"
            "5. Trust what you SEE, not the OCR history\n"
            "\n"
            "Output ONLY the timestamp. NO explanations."
        )
    }
}

# Mismatch Correction Prompts (Enhanced for 7B Verification with Dual Image Comparison)
MISMATCH_PROMPTS = {
    'STATUS': (
        "🔍 CONFLICT RESOLUTION - Status Indicator\n"
        "\n"
        "Dispute Details:\n"
        "  • Previous scan: '{compared_value}'\n"
        "  • Current scan: '{current_value}'\n"
        "  • Expected (typical): '{median_context}'\n"
        "  • These readings SHOULD match (redundant captures)\n"
        "\n"
        "Your Task:\n"
        "Look at this image with MAXIMUM precision and determine:\n"
        "  - Is it 'OK' (pass/good/zero defect)?\n"
        "  - Is it 'NG' (fail/bad/defect detected)?\n"
        "\n"
        "Critical Rules:\n"
        "1. Output ONLY 'OK' or 'NG' (nothing else)\n"
        "2. Trust what you SEE in the image, ignore OCR history\n"
        "3. If display shows '0' or 'O' → Usually means OK\n"
        "4. If display is blank/dark/unreadable → Output: NG\n"
        "5. Common patterns:\n"
        "   - 'OK', 'O', 'K', '0' → Output: OK\n"
        "   - 'NG', 'N', 'G' → Output: NG\n"
        "\n"
        "Think: Which reading ({compared_value} or {current_value}) matches what you see?"
    ),
    'INTEGER': (
        "🔍 DUAL IMAGE COMPARISON - Integer Value\n"
        "\n"
        "📸 You are viewing TWO images:\n"
        "  • Image 1 (Previous): From '{prev_filename}' - ROI_{roi_id}\n"
        "  • Image 2 (Current): From '{curr_filename}' - ROI_{roi_id}\n"
        "\n"
        "Dispute Details:\n"
        "  • Previous scan read: '{compared_value}'\n"
        "  • Current scan read: '{current_value}'\n"
        "  • Typical value (median): {median_context}\n"
        "  • These TWO images should show THE SAME number (redundant captures)\n"
        "\n"
        "Your Mission:\n"
        "Compare BOTH images and determine the TRUE integer value.\n"
        "\n"
        "🔴 CRITICAL ANALYSIS STEPS:\n"
        "1. Look at BOTH images side by side\n"
        "2. Check if they show the same number\n"
        "3. Identify which reading is correct\n"
        "4. Compare with median={median_context} for sanity check\n"
        "\n"
        "🚨 NOISE FILTERING (MUST FOLLOW):\n"
        "  ❌ IGNORE half-cut numbers at image edges\n"
        "  ❌ IGNORE numbers with only 50% or less visible\n"
        "  ❌ IGNORE text with different colored background that's cut off\n"
        "  ❌ IGNORE background patterns or decorative elements\n"
        "  ❌ DO NOT guess from partial digits - only read complete numbers\n"
        "  ✅ ONLY read fully visible digits in the main display area\n"
        "\n"
        "High Confidence Detection:\n"
        "  • Both images show same number → High confidence, output that number\n"
        "  • One image clearer than other → Use the clearer one\n"
        "  • Both unclear but one matches median → Probably correct\n"
        "  • Half-broken numbers in one image → Use the complete one\n"
        "\n"
        "Special Cases:\n"
        "  - Both show '0' or blank → Output: 0 (sensor failure)\n"
        "  - Both show 'NA' or error → Output: 0\n"
        "  - One shows partial digit (half-cut) → Ignore it, use complete number from other image\n"
        "\n"
        "Common OCR Errors:\n"
        "  • '1' vs 'l' vs 'I'\n"
        "  • '0' vs 'O'\n"
        "  • Missing leading/trailing digits\n"
        "\n"
        "Output ONLY the integer. NO explanations.\n"
        "Think: Do both images show the same number? Which one is complete and clear?"
    ),
    'FLOAT': (
        "🔍 DUAL IMAGE COMPARISON - Floating Point Measurement\n"
        "\n"
        "📸 You are viewing TWO images:\n"
        "  • Image 1 (Previous): From '{prev_filename}' - ROI_{roi_id}\n"
        "  • Image 2 (Current): From '{curr_filename}' - ROI_{roi_id}\n"
        "\n"
        "Dispute Details:\n"
        "  • Previous scan read: '{compared_value}'\n"
        "  • Current scan read: '{current_value}'\n"
        "  • Typical value (median): {median_context}\n"
        "  • These TWO images should show THE SAME number (redundant captures)\n"
        "\n"
        "Your Mission:\n"
        "Compare BOTH images and determine the TRUE floating-point value.\n"
        "\n"
        "🔴 CRITICAL - Decimal Point Position:\n"
        "This is the #1 source of errors!\n"
        "  • Display: '1.88' but OCR reads '188' → WRONG by 100x!\n"
        "  • Display: '0.52' but OCR reads '52' → WRONG by 100x!\n"
        "\n"
        "🔴 CRITICAL ANALYSIS STEPS:\n"
        "1. Look at BOTH images - do they show same number?\n"
        "2. Locate decimal point in EACH image\n"
        "3. Count digits before and after decimal in EACH\n"
        "4. Check for negative sign in EACH\n"
        "5. If one image clearer, trust that one\n"
        "6. Sanity check: close to median={median_context}?\n"
        "\n"
        "🚨 NOISE FILTERING (MUST FOLLOW):\n"
        "  ❌ IGNORE half-cut numbers at image edges\n"
        "  ❌ IGNORE numbers with only 50% or less visible\n"
        "  ❌ IGNORE text with different colored background that's cut off\n"
        "  ❌ IGNORE background patterns, decorative elements, or peripheral text\n"
        "  ❌ DO NOT guess from partial digits - only read complete numbers\n"
        "  ❌ If decimal point is in cut-off area, ignore that reading\n"
        "  ✅ ONLY read fully visible numbers with complete decimal point\n"
        "\n"
        "High Confidence Detection:\n"
        "  • Both images show same complete number → Output that number\n"
        "  • One image has half-cut digits → Use the complete one only\n"
        "  • One reading matches median, other is 10x or 100x off → Likely decimal error\n"
        "  • Both readings complete but different → Check which is closer to median\n"
        "\n"
        "Special Cases:\n"
        "  - Both show '0' or blank → Output: 0 (sensor failure/defect)\n"
        "  - Both show 'NA', 'ERR', 'OL' → Output: 0\n"
        "  - One has partial number, other is complete → Use complete number\n"
        "  - Both have half-cut decimals → Output: 0 (cannot read reliably)\n"
        "\n"
        "Format Rules:\n"
        "  • Maximum 3 decimal places (1.234 not 1.23456789)\n"
        "  • Remove trailing zeros (1.500 → 1.5)\n"
        "  • Include negative sign if present in BOTH images\n"
        "\n"
        "Context Analysis:\n"
        "Given median={median_context}:\n"
        "  - If one reading ≈ median but other is 100x → Decimal point error\n"
        "  - If both far from median → Might be real '0' (defect)\n"
        "\n"
        "Output ONLY the number (e.g., 1.88 or 0 or -0.52). NO units, NO explanations.\n"
        "Think: Do both images show the same complete number? Which one has all digits visible?"
    ),
    'TIME': (
        "🔍 CONFLICT RESOLUTION - Timestamp\n"
        "\n"
        "Dispute Details:\n"
        "  • Previous scan: '{compared_value}'\n"
        "  • Current scan: '{current_value}'\n"
        "  • These readings SHOULD match (redundant captures)\n"
        "\n"
        "Your Task:\n"
        "Read the timestamp from this display with precision.\n"
        "\n"
        "Critical Checks:\n"
        "1. Verify colon positions (HH:MM:SS format)\n"
        "2. Check all 6 digits are present\n"
        "3. Confirm 24-hour format (00-23 for hours)\n"
        "4. Look for any trailing text to remove\n"
        "\n"
        "Common OCR Errors:\n"
        "  • Colons ':' read as periods '.' or semicolons ';'\n"
        "  • Missing leading zeros (9:5:3 should be 09:05:03)\n"
        "  • Extra date information included\n"
        "\n"
        "Special Cases:\n"
        "  - If display is blank/dark → Output: NA\n"
        "  - If format is corrupted → Output: NA\n"
        "\n"
        "Output format: HH:MM:SS (e.g., 14:35:22)\n"
        "Think: Which reading ({compared_value} or {current_value}) matches the display?"
    )
}

# ================= 日志配置 / Logging Configuration =================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

def get_similarity_threshold(csv_name: str) -> float:
    """根据CSV文件名获取相应的相似度阈值"""
    for key in SIMILARITY_THRESHOLDS:
        if key in csv_name:
            return SIMILARITY_THRESHOLDS[key]
    return DEFAULT_SIMILARITY_THRESHOLD

def get_roi_type(roi_id: str) -> str:
    """获取ROI的数据类型"""
    return ROI_TYPE_MAP.get(roi_id, 'STATUS')

def get_prompt(roi_id: str, prompt_type: str = 'initial', 
               ocr_value: str = '', median_value: float = None,
               compared_value: str = '', current_value: str = '',
               prev_filename: str = '', curr_filename: str = '') -> str:
    """
    根据ROI类型和上下文生成prompt
    
    Args:
        roi_id: ROI标识符（如 'ROI_13'）
        prompt_type: 'initial', 'correction', 或 'mismatch'
        ocr_value: 之前的OCR结果（用于correction）
        median_value: 该ROI的中位数值（用于上下文提示）
        compared_value: 比较值（用于mismatch）
        current_value: 当前值（用于mismatch）
        prev_filename: 前一张图像文件名（用于mismatch dual comparison）
        curr_filename: 当前图像文件名（用于mismatch dual comparison）
    """
    roi_type = get_roi_type(roi_id)
    
    # 选择prompt模板
    if prompt_type == 'mismatch':
        template = MISMATCH_PROMPTS.get(roi_type, MISMATCH_PROMPTS['STATUS'])
    else:
        template = PROMPTS.get(roi_type, {}).get(prompt_type, PROMPTS['STATUS']['initial'])
    
    # 格式化median上下文
    median_context = "No reference available"
    if median_value is not None:
        if roi_type == 'STATUS':
            # 对于STATUS，显示最常见的值
            median_context = f"Most common: {median_value}"
        elif roi_type == 'INTEGER':
            median_context = f"{int(median_value)}"
        elif roi_type == 'FLOAT':
            median_context = f"{median_value:.3f}"
        elif roi_type == 'TIME':
            median_context = "Timestamp (varies)"
    
    # 替换所有占位符
    prompt = template.replace('{ocr_value}', str(ocr_value))
    prompt = prompt.replace('{median_context}', str(median_context))
    prompt = prompt.replace('{compared_value}', str(compared_value))
    prompt = prompt.replace('{current_value}', str(current_value))
    prompt = prompt.replace('{prev_filename}', str(prev_filename))
    prompt = prompt.replace('{curr_filename}', str(curr_filename))
    prompt = prompt.replace('{roi_id}', str(roi_id).replace('ROI_', ''))
    
    return prompt

def create_directories():
    """创建所有必要的目录"""
    dirs = [
        SOURCE_DIR, OUTPUT_BASE, STAGE_1_OCR, STAGE_2_CLEANED,
        STAGE_3_3B_CORRECTED, STAGE_4_LABELED, STAGE_5_7B_VERIFIED,
        STAGE_6_FINAL, DEBUG_CROPS_BASE, ABNORMAL_CROPS_BASE,
        REDUNDANCY_CROPS_BASE
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("✅ All directories created successfully")

if __name__ == "__main__":
    print("Configuration loaded successfully")
    print(f"Server Root: {SERVER_ROOT}")
    print(f"OCR Model 3B: {OLLAMA_MODEL_3B}")
    print(f"OCR Model 7B: {OLLAMA_MODEL_7B}")
    print(f"\nROI Type Map: {len(ROI_TYPE_MAP)} ROIs configured")
    print(f"CSV Groups: {len(CSV_GROUPS)} groups configured")
    create_directories()

