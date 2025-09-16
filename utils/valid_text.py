import re
import unicodedata as ud

known_tokens = " '%?!,+():~&*-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyzᄀᄁᄂᄃᄄᄅᄆᄇᄈᄉᄊᄋᄌᄍᄎᄏᄐᄑ하ᅢᅣᅤᅥᅦᅧᅨᅩᅪᅫᅬᅭᅮᅯᅰᅱᅲᅳᅴᅵᆨᆩᆪᆫᆬᆭᆮᆯᆰᆱᆲᆳᆴᆵᆶᆷᆸᆹᆺᆻᆼᆽᆾᆿᇀᇁᇂ"

def is_valid_text(s):
    # 의심 패턴 체크
    invalid_patterns = [
        r'[\t\n]',              # 탭/개행 문자
        r'\s{2,}'               # 2칸 이상 공백
    ]
    for pat in invalid_patterns:
        if re.search(pat, s):
            return False

    # jamo로 분해 후 unknown token 체크
    jamo_text = ud.normalize('NFD', s)
    for ch in jamo_text:
        if ch not in known_tokens:
            return False
    return True