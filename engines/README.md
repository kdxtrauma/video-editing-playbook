# Исполняемый контур
autonomy.py — независимое ядро валидатора и оценки, Python 3.9+, без сторонних пакетов. Оно не вызывает LLM и не рендерит NLE: реальные вызовы выполняет Harness через свои адаптеры. Оно проверяет план, предлагает релевантные карточки, рассчитывает результат QC и определяет переход состояния. Подключить функции напрямую или CLI. media_probe.py — реальная инвентаризация и decode FFmpeg. Существующие tools/podcast_edit_engine.py и tools/podcast_director.py не изменены.
Команды из корня:
    python engines/autonomy.py skills direction footage --limit 8
    python engines/autonomy.py validate engines/example-plan.json
    python engines/autonomy.py review engines/example-review.json
    python engines/autonomy.py next REVIEW --review engines/example-review.json --attempt 0 --max-attempts 3
    python engines/media_probe.py path/to/master.mp4 --decode
    python -m unittest discover -s engines/tests -v
Интерфейс плана: fps {num,den}, duration_frames, assets [{id,duration_frames,rights}], clips [{asset_id,source_in,source_out,timeline_in,timeline_out,track,reason}]. Все интервалы [in,out) в нормализованном CFR timebase, прямые склейки без ретайма; адаптер обязан нормализовать VFR или использовать собственный точный контракт. V1 не описывает произвольный compositing, retime, многоканальный sound design. Расширять schema, не делать вид, что unsupported операция выполнена.
Интерфейс review: artifact_sha256, gates (truth, rights, privacy, decode, specs, observation), scores (story,rhythm,picture,sound,graphics,style,delivery), evidence по каждой оси, defects с severity/evidence. artifact hash в примере синтетический, не мастер. Счёт не заменяет независимое наблюдение.
Оркестратор Harness: загрузить roles.json → capability probe → вызвать producer → две независимые director роли → judge → editor/специалисты → validate → реальный executor → hash/export → critic → review → next → repair/re-render → повторить → release или blocked. Сохранить checkpoint после каждой стадии; использовать local artifacts. Сильная модель не считается критиком, если она не получила артефакт. Перед публикацией только явное разрешение.

## Полный управляющий запуск
[Протокол pipeline.py](protocol.md) описывает реальные вызовы локальных адаптеров, независимые концепции, executor, critic и repair. [FFmpeg V1 executor](ffmpeg-executor.md) — ограниченный реальный multi-source cut-only адаптер. Он не заменяет интеграции для сложного монтажа.

## Layered v2
[Layered Executor](layered-executor.md) implements a typed visual, title, sound cue and simple grade layer on top of the V1 plan. Choose it explicitly and give the editor its schema; V1 rejects nonempty layers. Other unsupported creative operations require a separate adapter.
