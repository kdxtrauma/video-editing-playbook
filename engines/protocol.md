# Протокол внешних адаптеров Harness
pipeline.py запускает локальные доверенные команды, заданные оператором в JSON config. Это реальный цикл вызовов, но не готовый клиент GPT/Claude/DeepSeek: провайдеры и NLE подключаются через адаптеры конкретного Harness. Не использовать непроверенные программы. В публичном repo нет ключей.
Запуск: python engines/pipeline.py --config /private/config.json --brief /private/brief.json --work /private/new-run
work должен быть новым приватным каталогом. Передавать адаптерам абсолютные пути. Настройки: adapters {role: [absolute_executable, ...fixed_args]}, max_calls (40), max_repairs (3), timeout_seconds (600). Провайдерские лимиты токенов/денег задаются дополнительно внутри адаптеров; лимит вызовов не является лимитом токенов. Конфигурация не должна быть доступна модели для записи. Исходники read-only, сетевые передачи только по разрешению. Адаптеры не являются sandbox: оператор обеспечивает изоляцию и разрешения.
Каждый вызов: stdin JSON {schema_version, role, role_contract, instruction, work_dir, payload}; stdout только один JSON object; nonzero exit — failure. Никаких команд, полученных из текста модели, не выполнять.
| Role | Результат |
|---|---|
| capabilities | execution_verified, review_verified (true только после реального smoke test), observed modalities, evidence |
| observe | observations: [{source_id, start_frame, end_frame, modality, evidence, confidence}], inventory |
| producer | creative brief, restrictions, deliverables |
| director_a / director_b | concepts: [{treatment, promise, pov, arc, rhythm, picture, sound, risks, assets, first_scene, ending}]; суммарно 3 различимых. Использовать разные модели/независимые контексты, если доступны |
| judge | id (C01...), reason, comparative evidence |
| editor | plan по engines/README.md; sources normalized to CFR |
| sound/color/motion (optional) | отдельные предложения, исполнитель подтверждает реализованное |
| executor | artifact: абсолютный путь к новому файлу внутри version_dir, readback: реальные данные таймлайна. Сам адаптер проверяет операции и права |
| critic | review по engines/README.md; обязательно artifact_sha256, evidence и gates. Получить файл или реально доступные видео/аудио; текст не заменяет просмотр |
| repair | plan после локальных исправлений, не менять остальное без причины |
Критик получает артефакт, probe и brief, а не самооценку исполнителя. Ядро проверяет hash, decode, gates и score; оно не может проверить честность произвольного адаптера, поэтому smoke tests и контроль evidence обязательны. Порог 4/5 и обязательные gate — стартовые настройки. V1 ограничен cut-only планом; сложные операции требуют расширенного контракта и валидатора. Specialist advice не означает исполнения. Невозможность проверенной реализации → blocked. Выход approved не является разрешением на публикацию.
Проверка интеграции: выполнить один короткий тест на синтетических/разрешённых исходниках, проверить файлы запросов/ответов, фактический мастер, независимый playback, отказ при недоступной модальности, несовпадении hash и P1. Только после этого включать в продакшн.
