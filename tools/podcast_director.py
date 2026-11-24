"""DeepSeek Harness podcast workflow. Python 3.8+, standard library."""
import argparse
import json
import os
import re
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET

VERSION = "1.0"
FOLDER = "podcast-director"
MARK = "<!-- khisomov-podcast-director-v1 -->"
RULES = """# Режиссура подкастов доктора Хисомова · версия 1.0

Применяй в этой рабочей папке при монтаже подкаста и его коротких версий. Команда «смонтируй выпуск» запускает весь цикл до экспорта. Вначале прочитай preferences.md рядом с этим файлом. Конкретное задание автора важнее прежних предпочтений. Используй мастер-промпт Zane для оформления, если он доступен. Сначала закончи речь. Проект и журнал решений должны пережить закрытие чата.

## Кто за что отвечает
Flash ведёт проект, управляет Resolve, собирает таймлайн и проверяет результат. Вызови отдельного Sonnet 5.5 для просмотра материала, отбора дублей и независимого разбора черновика. Проверь в метаданных реального вызова провайдера и модель. Если вызов недоступен, отметь это и выполни доступные этапы. Только Flash пишет в текущий таймлайн. При повторном запуске открой последний рабочий монтаж и сравни его с планом перед изменениями. Сохрани прежнюю версию.

## Прежде чем резать
Прочитай имя активного проекта, частоту, таймлайн и доступные исходники через реальную связь с Resolve. Исходные файлы и эталонный таймлайн сохрани. Работай в отдельной копии. Если проект уже содержит расставленные кадры, изучи их до импорта. Уточни лишь реально неоднозначный исходник. Для вертикального Reels из новой записи базовый формат 1080×1920 с частотой исходника; для полного подкаста сохрани заданные формат и длительность. Не сокращай длинный выпуск до Reels по умолчанию.

## Как разбирать эталон
Используй одобренный автором готовый монтаж. Посмотри изображение, послушай звук, прочитай доступную раскадровку. Если доступна только расшифровка, оценивай только речь. Если инструмент не принимает видео целиком, извлеки кадры вокруг стыков и короткие звуковые отрывки; сообщи, какие каналы реально проверил.
Выбери показательные места, включая удачную склейку и, если она есть, намеренно оставленную паузу. Для каждого сохрани в папке выпуска таймкод готовой версии, что слышит зритель до и после, что меняется на экране, зачем решение подходит этой реплике. Сформулируй переносимый приём и случай, когда он испортит другой эпизод. Длина плана в одном эталоне не задаёт обязательный интервал нарезки.

## Как режиссировать новый материал
Прослушай запись целиком. Сформулируй одним предложением, с каким вопросом зритель входит в историю и какой ответ получает в конце. Разметь удачные полные дубли, самопоправки, незавершённые мысли, смысловые оговорки и моменты, когда лицо рассказывает больше вставки. Для каждого выбранного отрезка сохрани файл, вход, выход и услышанные первые и последние слова. Различай время на исходнике и на готовом таймлайне.
При выборе между дублями сначала проверь точность смысла, затем естественность речи и непрерывность движения. Удачная запинка может звучать живее гладкого дубля. Если первый вопрос уже создаёт интерес, начинай с него. Если он понятен лишь после предыдущей реплики, верни контекст. Не придумывай слова врача и реплики пациентов. Если в полном подкасте говорит собеседник, сохраняй вопрос или реакцию, от которых зависит ответ.
На каждой спорной склейке сравни удержание кадра с одной мотивированной заменой. Что зритель должен заметить именно на этом слове? Дай движению руки завершиться, когда оно объясняет мысль. Срежь повторный заход, когда он только откладывает следующую мысль. Используй перебивку, если она показывает конкретную деталь или помогает скрыть неизбежный скачок. МРТ и схема должны относиться к тому, что автор объясняет. Сгенерированную картинку не выдавай за исследование пациента.
Пример рассуждения: «Мне диагноз уже три раза ставили… А что он значит — впервые объяснили». Сначала попробуй оставить лицо и паузу между фразами. На второй фразе проверь, усиливает ли реакция развязку. Перебивка на случайный кабинет в этот момент лишает зрителя реакции. Другой пример: на «посмотрите вот сюда» слушатель ждёт указанный объект; покажи соответствующий фрагмент, удержи его достаточно для чтения и верни лицо к следующей мысли. Это примеры выбора, а не реплики для вставки.
Перед удалением проверяй область действия отрицаний, слов «иногда», «если», «только», дозировок и временных условий. Сравни утверждение до и после склейки. При смысловой неоднозначности сохрани полностью произнесённую мысль. Береги чередование «реплика — реакция — объяснение», юмор и голос автора. Не добавляй драматическую музыку только потому, что упомянут диагноз.

## Монтаж, который можно проверить
До записи в Resolve зафиксируй монтажный лист отдельно от результата. Для простого черновика с одной речевой дорожкой используй план JSON из справки программы. Экспортируй фактический FCPXML из рабочего таймлайна после сборки. Запусти команду audit. Нельзя получать фактические стыки копированием собственного плана. Исправляй расхождения на таймлайне, экспортируй заново. Изменение плана допустимо, если принято новое режиссёрское решение; запиши его причину до повторной проверки.
Если тип монтажа выходит за возможности проверки (мультикам, J/L-склейки, переходы, смешанные FPS), не упрощай удачный монтаж ради зелёного статуса. Считай ID источника и границы клипов отдельно на используемых видео- и аудиодорожках средствами установленной версии Resolve, сверь с планом, проверь смещение и синхронность вокруг стыков. При отсутствии доступа запиши, какие стыки остались без проверки.
Прослушай черновик без графики. На каждом изменённом стыке проверь последнее и первое слово, вдох, шум комнаты и обрыв хвоста согласной. Посмотри этот участок в движении. Если заметен скачок, сравни соседнюю точку входа, альтернативный дубль и перебивку. Если использовал J/L-склейку, проверь, что звук и изображение снова сходятся там, где видны губы. Sonnet получает именно экспорт черновика или доступные фрагменты. Пусть укажет таймкод, наблюдаемый дефект и одну целевую правку. По результату исправь только подтверждённые дефекты.

## Оформление и сдача
После утверждения структуры добавь субтитры по финальной речи, предметные подписи и графику, музыку и эффекты из библиотеки; примени условия мастер-промпта для конкретного выпуска. Сохраняй читаемость на телефоне. Выравнивай музыку под репликами и прослушивай стыки. Если в задаче не задана громкость, не выдавай произвольную цифру за норму площадки. Для новых платных генераций нужен заданный бюджет.
Для повторного использования держи общие медиа в постоянной папке; собери общие корзины либо проект-шаблон. На втором проекте или его копии проверь доступность реального файла, а не только наличие имени в корзине. Каждый выпуск получает собственный таймлайн, папку материалов и экспорт.
Открой готовый MP4 вне таймлайна, проверь длительность, речь, вшитые субтитры и начало/конец. Код проверки склеек не проверяет картинку, звук, медицину или вкус. В отчёте дай путь к файлу, проект/таймлайн, что проверено по воспроизведению и что осталось непроверенным. Ничего не публикуй.

## Как накапливать вкус автора
Если автор даёт правку, зафиксируй таймкод, его слова, редакцию до/после и причину. Разовое «здесь подержи паузу» исправляет этот фрагмент. Прямое «в следующих выпусках всегда делай так» запиши в preferences.md как постоянную установку с датой и областью применения. Если правка кажется повторяющимся предпочтением, сохрани гипотезу в журнале выпуска до подтверждения. При смене предпочтения запиши новую формулировку и явно пометь прежнюю как заменённую. Перед следующим выпуском прочитай активные решения.
"""
FORMAT = """audit PLAN.json TIMELINE.fcpxml
Plan for a straight dialogue rough cut (one project, primary spine, normal
speed, equal source/timeline frame durations, no transitions or overlays):
{"timeline":"Rough v1","fps":"25","clips":[
 {"file":"A.mp4","source_in":50,"source_out":90},
 {"file":"A.mp4","source_in":150,"source_out":215}]}
Paths in the plan use the exact unique media basename. Use rational FPS such
as "30000/1001". Source frames are relative to each media file start; out is
exclusive. Capture the plan BEFORE editing. Pass a fresh FCPXML from Resolve
for the actual edit. Exit 0 = boundaries match; 1 = mismatch/unsupported.
"""
def save(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(data)
    try:
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()

def install(root):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Укажите рабочую папку Harness.")
    dest = root / FOLDER
    dest.mkdir(exist_ok=True)
    rules = dest / "director.md"
    prefs = dest / "preferences.md"
    script = dest / "podcast_director.py"
    for path, data in [(rules, RULES.encode()), (script, Path(__file__).read_bytes())]:
        if path.exists() and path.read_bytes() != data:
            raise ValueError("Существует другая версия. Сохраните её и сравните: " + str(path))
        if not path.exists():
            save(path, data)
    if not prefs.exists():
        save(prefs, "# Подтверждённые предпочтения автора\n".encode())
    entry = root / "AGENTS.md"
    previous = entry.read_bytes() if entry.exists() else b""
    previous.decode("utf-8-sig")
    if MARK.encode() not in previous:
        if entry.exists():
            with NamedTemporaryFile(prefix="AGENTS-backup-", suffix=".md", dir=dest, delete=False) as backup:
                backup.write(previous)
        note = (f"\n\n{MARK}\nДля монтажа каждого подкаста или Reels прочитай "
                "podcast-director/director.md и podcast-director/preferences.md до работы. "
                "Для проверки прямых склеек используй podcast-director/podcast_director.py audit.\n")
        save(entry, previous + note.encode())
    print("Правила проекта:", rules, "Версия:", VERSION)

def sec(text):
    if not text or not re.fullmatch(r"-?\d+(?:/\d+)?s", text):
        raise ValueError("Неподдерживаемая запись времени: " + str(text))
    return Fraction(text[:-1])

def frames(seconds, fps):
    count = seconds * fps
    if count.denominator != 1:
        raise ValueError("Граница не совпадает с кадром")
    return int(count)

def audit(plan_file, xml_file):
    from urllib.parse import unquote, urlparse
    p = json.loads(plan_file.read_text(encoding="utf-8-sig"), parse_float=Decimal)
    fps = Fraction(str(p["fps"]))
    if fps <= 0 or not p["clips"]:
        raise ValueError("Нужны положительный FPS и непустой план.")
    expected = []
    for clip in p["clips"]:
        start, end = clip["source_in"], clip["source_out"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end:
            raise ValueError("Ошибка диапазона в плане.")
        expected.append((clip["file"], start, end))
    root = ET.parse(xml_file).getroot()
    projects = root.findall(".//project")
    if len(projects) != 1 or projects[0].get("name") != p["timeline"]:
        raise ValueError("Выберите экспорт одного указанного таймлайна.")
    seq = projects[0].find("sequence")
    res = {r.get("id"): r for r in root.findall("./resources/*")}
    if seq is None or sec(res[seq.get("format")].get("frameDuration")) * fps != 1:
        raise ValueError("Частота таймлайна отличается от плана.")
    spine = seq.find("spine")
    if spine is None or len(spine) == 0:
        raise ValueError("Нет доступной монтажной последовательности.")
    actual, names = [], {}
    cursor = sec(seq.get("tcStart", "0s"))
    origin = cursor
    for item in spine:
        if item.tag != "asset-clip" or item.get("enabled","1") != "1" or any(
            n.tag in {"timeMap","spine","asset-clip","clip","ref-clip","video","audio","mc-clip","sync-clip","transition","gap"} for n in list(item.iter())[1:]):
            raise ValueError("Сложная или выключенная склейка. Проверьте дорожки в Resolve.")
        if sec(item.get("offset")) != cursor:
            raise ValueError("Разрыв или перекрытие на основном таймлайне.")
        asset = res[item.attrib["ref"]]
        if asset.tag != "asset" or sec(res[asset.attrib["format"]].get("frameDuration")) * fps != 1:
            raise ValueError("Неподдерживаемый источник или смешанные FPS.")
        src = asset.get("src")
        if not src:
            orig = asset.find("media-rep[@kind='original-media']")
            src = orig.get("src") if orig is not None else None
        if not src:
            raise ValueError("Нет пути к оригинальному медиа.")
        name = unquote(urlparse(src).path).replace(chr(92),"/").split("/")[-1]
        if name in names and names[name] != src:
            raise ValueError("Разные источники с одинаковым именем: " + name)
        names[name] = src
        duration = sec(item.attrib["duration"])
        start = frames(sec(item.get("start","0s")) - sec(asset.get("start","0s")), fps)
        actual.append((name, start, start + frames(duration, fps)))
        cursor += duration
    if sec(seq.attrib["duration"]) != cursor - origin:
        raise ValueError("Длительность последовательности отличается от суммы клипов.")
    if expected != actual:
        from itertools import zip_longest
        for i, (wanted, found) in enumerate(zip_longest(expected, actual), 1):
            if wanted != found:
                print(f"Фрагмент {i}: план {wanted}; прочитано {found}")
        raise ValueError("Склейки не совпали с планом.")
    print(f"Совпадение: {len(actual)} фрагментов, {frames(cursor-origin,fps)} кадров.")

def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=FORMAT, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("install").add_argument("workspace", type=Path)
    check = sub.add_parser("audit", description=FORMAT, formatter_class=argparse.RawDescriptionHelpFormatter)
    check.add_argument("plan", type=Path)
    check.add_argument("fcpxml", type=Path)
    a = parser.parse_args()
    try:
        if a.action == "install":
            install(a.workspace)
        else:
            audit(a.plan, a.fcpxml)
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError, ZeroDivisionError) as exc:
        sys.exit("Не подтверждено: " + str(exc))
if __name__ == "__main__":
    main()
