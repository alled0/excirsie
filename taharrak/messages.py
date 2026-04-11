"""
English / Arabic message dictionaries for Taharrak.
Arabic text rendering uses PIL + arabic-reshaper + python-bidi if available,
otherwise falls back to English text via OpenCV.
"""

import numpy as np
import cv2

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    from PIL import Image, ImageDraw, ImageFont
    _AR_OK = True
except ImportError:
    _AR_OK = False

# ── Message tables ────────────────────────────────────────────────────────────

MESSAGES = {
    "en": {
        "app_title":        "TAHARRAK — AI FITNESS",
        "select_exercise":  "Select Exercise",
        "history":          "H: History",
        "lang_toggle":      "L: العربية",
        "quit_hint":        "Q: Quit",
        "weight_input":     "Enter Weight (kg)",
        "weight_hint":      "UP/DOWN to adjust   SPACE to confirm   ESC to go back",
        "suggest_increase": "Consider +{n} kg",
        "calibration_hint": "Stand ~1.5 m away · raise both arms · camera at shoulder height",
        "no_person":        "No person detected",
        "improve_hint":     "Move closer · improve lighting · show both arms",
        "space_start":      "SPACE  to begin workout",
        "target_hint":      "Target: {n} reps per set",
        "need_good":        "Both arms must show GOOD before starting",
        "get_ready":        "GET READY",
        "go":               "Go!",
        "set_label":        "SET {n}",
        "warmup_badge":     "WARM-UP",
        "too_fast":         "TOO FAST",
        "tempo_label":      "TEMPO",
        "det_label":        "DET:",
        "avg_label":        "Avg",
        "target_label":     "/ {n}",
        "set_done_banner":  "Set {n} complete!  Press S for rest",
        "fatigue_warning":  "Fatigue detected — consider stopping",
        "sym_lag":          "{side} arm lagging — focus on weak side",
        "extend_fully":     "[{side}] Extend fully at the bottom",
        "curl_fully":       "[{side}] Squeeze all the way up!",
        "swing_warn":       "{side} body swing — brace your core!",
        "slow_down":        "[{side}] Slow down — control the movement",
        "lower_slowly":     "[{side}] Lower slowly with control",
        "curl_up":          "[{side}] Curl up!",
        "press_up":         "[{side}] Press up!",
        "raise_up":         "[{side}] Raise up!",
        "set_rest_title":   "SET {n} COMPLETE",
        "rest_title":       "REST",
        "space_skip":       "SPACE to skip rest",
        "summary_title":    "TAHARRAK — SESSION SUMMARY",
        "sets_label":       "Sets completed: {n}",
        "form_section":     "FORM",
        "sym_section":      "SYMMETRY",
        "rating_section":   "OVERALL RATING",
        "session_avg":      "Session avg: {avg}/100     Best rep: {best}/100",
        "sym_good":         "Excellent symmetry between arms!",
        "sym_weak":         "{side} arm weaker by {diff} pts — prioritise next session",
        "rep_diff":         "{side} arm did {n} fewer total reps",
        "closing":          "Closing in {n}s  —  press any key to close now",
        "rating_S":         "Flawless form",
        "rating_A":         "Great session",
        "rating_B":         "Solid work",
        "rating_C":         "Keep practising",
        "history_title":    "SESSION HISTORY",
        "history_empty":    "No sessions recorded yet for this exercise",
        "history_hint":     "ESC to go back",
        "history_header":   "  DATE              REPS  SETS  AVG   BEST  RATING  WEIGHT",
        "pb_label":         "Personal Best",
        "left":             "LEFT",
        "right":            "RIGHT",
        "controls_workout": "S:end set   R:reset set   Q:finish session",
        "controls_select":  "1-5:exercise   H:history   L:language   Q:quit",
        # Camera position feedback
        "cam_feedback_title": "Camera Position Check",
        "cam_good":           "Camera position: GOOD",
        "cam_too_close":      "Step back — you're too close",
        "cam_too_far":        "Step forward — you're too far",
        "cam_too_low":        "Camera too low — raise it to shoulder height",
        "cam_too_high":       "Camera too high — lower it",
        "cam_move_right":     "Move right — you're off center",
        "cam_move_left":      "Move left — you're off center",
        "cam_turn_left":      "Turn slightly left to face camera",
        "cam_turn_right":     "Turn slightly right to face camera",
        "cam_poor_vis":       "Poor visibility — improve lighting",
        "joint_hidden":       "Key joint not visible — extend arm into frame",
    },
    "ar": {
        "app_title":        "تحرك — لياقة بالذكاء الاصطناعي",
        "select_exercise":  "اختر تمريناً",
        "history":          "H: السجل",
        "lang_toggle":      "L: English",
        "quit_hint":        "Q: خروج",
        "weight_input":     "أدخل الوزن (كجم)",
        "weight_hint":      "أعلى/أسفل للضبط   مسافة للتأكيد   ESC للرجوع",
        "suggest_increase": "فكّر في +{n} كجم",
        "calibration_hint": "قف على بُعد ١.٥ م · ارفع ذراعيك · الكاميرا على مستوى الكتف",
        "no_person":        "لا يوجد شخص",
        "improve_hint":     "اقترب · حسّن الإضاءة · أظهر كلا الذراعين",
        "space_start":      "مسافة  للبدء",
        "target_hint":      "الهدف: {n} تكرار",
        "need_good":        "يجب أن تكون الذراعان جيدتين قبل البدء",
        "get_ready":        "استعد",
        "go":               "ابدأ!",
        "set_label":        "المجموعة {n}",
        "warmup_badge":     "إحماء",
        "too_fast":         "سريع جداً",
        "tempo_label":      "الإيقاع",
        "det_label":        "كشف:",
        "avg_label":        "متوسط",
        "target_label":     "/ {n}",
        "set_done_banner":  "المجموعة {n} اكتملت!  اضغط S للراحة",
        "fatigue_warning":  "يُرصد إجهاد — فكّر في التوقف",
        "sym_lag":          "ذراع {side} متأخرة — ركّز عليها",
        "extend_fully":     "[{side}] مدّ ذراعك بالكامل",
        "curl_fully":       "[{side}] اثنِ حتى النهاية!",
        "swing_warn":       "تأرجح {side} — شدّ بطنك!",
        "slow_down":        "[{side}] أبطئ — تحكّم في الحركة",
        "lower_slowly":     "[{side}] أنزل ببطء",
        "curl_up":          "[{side}] ارفع!",
        "press_up":         "[{side}] اضغط للأعلى!",
        "raise_up":         "[{side}] ارفع!",
        "set_rest_title":   "المجموعة {n} اكتملت",
        "rest_title":       "استراحة",
        "space_skip":       "مسافة لتخطي الاستراحة",
        "summary_title":    "تحرك — ملخص الجلسة",
        "sets_label":       "المجموعات: {n}",
        "form_section":     "الأداء",
        "sym_section":      "التماثل",
        "rating_section":   "التقييم الكلي",
        "session_avg":      "المتوسط: {avg}/100     أفضل تكرار: {best}/100",
        "sym_good":         "تماثل ممتاز بين الذراعين!",
        "sym_weak":         "ذراع {side} أضعف بـ{diff} نقطة",
        "rep_diff":         "ذراع {side} أقل بـ{n} تكرار",
        "closing":          "الإغلاق في {n}ث  —  اضغط أي مفتاح للإغلاق",
        "rating_S":         "أداء مثالي",
        "rating_A":         "جلسة ممتازة",
        "rating_B":         "عمل جيد",
        "rating_C":         "واصل التدريب",
        "history_title":    "سجل الجلسات",
        "history_empty":    "لا توجد جلسات مسجلة بعد",
        "history_hint":     "ESC للرجوع",
        "history_header":   "  التاريخ              تكرار  مجم  متوسط  أفضل  تقييم  وزن",
        "pb_label":         "أفضل إنجاز",
        "left":             "يسار",
        "right":            "يمين",
        "controls_workout": "S:إنهاء  R:إعادة  Q:إنهاء الجلسة",
        "controls_select":  "١-٥:تمرين  H:سجل  L:لغة  Q:خروج",
        # Camera position feedback
        "cam_feedback_title": "التحقق من وضع الكاميرا",
        "cam_good":           "وضع الكاميرا: جيد",
        "cam_too_close":      "تراجع للخلف — أنت قريب جداً",
        "cam_too_far":        "تقدم للأمام — أنت بعيد جداً",
        "cam_too_low":        "الكاميرا منخفضة — ارفعها إلى مستوى الكتف",
        "cam_too_high":       "الكاميرا مرتفعة — أنزلها",
        "cam_move_right":     "تحرك يميناً — لست في المنتصف",
        "cam_move_left":      "تحرك يساراً — لست في المنتصف",
        "cam_turn_left":      "استدر قليلاً لليسار",
        "cam_turn_right":     "استدر قليلاً لليمين",
        "cam_poor_vis":       "الرؤية ضعيفة — حسّن الإضاءة",
        "joint_hidden":       "مفصل رئيسي مخفي — أظهر ذراعك في الإطار",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Get translated string, falling back to English."""
    text = MESSAGES.get(lang, MESSAGES["en"]).get(key, MESSAGES["en"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


# ── Arabic text rendering ──────────────────────────────────────────────────────

_font_cache: dict = {}

def _load_font(font_path: str, size: int):
    key = (font_path, size)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(font_path, size)
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def put_text(img, text: str, pos: tuple, scale: float = 0.8,
             color=(255, 255, 255), thickness: int = 2,
             lang: str = "en", font_path: str = ""):
    """
    Renders text onto img at pos. Uses PIL for Arabic, OpenCV for English.
    """
    if lang == "ar" and _AR_OK and font_path and text.strip():
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        pil_img  = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw     = ImageDraw.Draw(pil_img)
        font_sz  = max(12, int(scale * 28))
        font     = _load_font(font_path, font_sz)
        # Right-align Arabic from pos
        bbox     = draw.textbbox((0, 0), bidi_text, font=font)
        tw       = bbox[2] - bbox[0]
        x        = max(0, pos[0] - tw)
        draw.text((x, pos[1] - font_sz), bidi_text, font=font,
                  fill=(color[2], color[1], color[0]))
        result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        img[:] = result
    else:
        cv2.putText(img, text, pos, cv2.FONT_HERSHEY_DUPLEX,
                    scale, color, thickness, cv2.LINE_AA)
