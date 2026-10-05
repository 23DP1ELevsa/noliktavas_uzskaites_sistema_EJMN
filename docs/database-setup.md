# Подключение MySQL

Миграция `0001_stockflow` создаёт девять таблиц из раздела 2.3 документа
`2 daļa.docx`. В карточке Trello указано восемь, но утверждённая схема содержит
девять; отдельной таблицы поставщиков в ней нет. Подробности:
[схема и принятые решения](database-schema.md).

## Локальный MySQL через Docker

Установите Docker Desktop, запустите его и выполните из корня проекта:

```powershell
docker compose up -d --wait
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m flask --app run db-check
.\.venv\Scripts\python.exe run.py
```

Копирование `.env` требуется только при первом запуске; существующий файл
с настройками сохраняйте. Задайте случайный `SECRET_KEY`. MySQL 8.4 из
`compose.yaml` создаёт базу `stockflow` и пользователя `stockflow` с локальным
паролем `stockflow`, соответствующим `.env.example`. Данные сохраняются в Docker
volume, порт доступен только через `127.0.0.1`. Пароли контейнера можно задать
переменными `MYSQL_PASSWORD` и `MYSQL_ROOT_PASSWORD` до первой инициализации;
при смене пароля пользователя обновите также `DATABASE_URL`.

Если виртуальной среды ещё нет: `py -m venv .venv`.
Остановить контейнер с сохранением данных: `docker compose stop`.

## Уже установленный MySQL

Нужен MySQL 8.0.16+ с работающими CHECK-ограничениями; рекомендуемая версия — 8.4.

1. Установите и запустите MySQL 8.4. Под административной учётной записью выполните:

   ```sql
   CREATE DATABASE IF NOT EXISTS stockflow
     CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER IF NOT EXISTS 'stockflow'@'localhost' IDENTIFIED BY 'replace-this-password';
   GRANT ALL PRIVILEGES ON stockflow.* TO 'stockflow'@'localhost';
   ```

2. Скопируйте `.env.example` в `.env`, задайте `SECRET_KEY` и строку подключения:

   ```dotenv
   DATABASE_URL=mysql+pymysql://stockflow:replace-this-password@localhost:3306/stockflow?charset=utf8mb4
   ```

   Специальные символы в имени пользователя и пароле нужно URL-кодировать
   (например, `@` → `%40`). `.env` исключён из Git.

3. Установите зависимости из корня проекта:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Примените миграцию и проверьте соединение:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run db upgrade
   .\.venv\Scripts\python.exe -m flask --app run db-check
   ```

   Повторный запуск применяет только ещё не выполненные миграции.
   Само приложение при запуске не создаёт и не удаляет таблицы.
   `db-check` проверяет соединение и наличие девяти таблиц, не меняя данные.
   `/health` остаётся проверкой доступности Flask.

## Railway — действия вне кода

1. Добавьте сервис **MySQL** в проект Railway.
2. Если Flask размещён в том же проекте и окружении Railway, в Variables сервиса
   Flask добавьте `DATABASE_URL=${{MySQL.MYSQL_URL}}`. Если сервис базы называется
   иначе, замените `MySQL` на его имя. Задайте отдельный случайный `SECRET_KEY`.
3. Для локального Flask, подключающегося к Railway, включите Public Access
   в Settings → Networking сервиса MySQL. Скопируйте значение `MYSQL_PUBLIC_URL`
   в `DATABASE_URL` локального `.env`. Внутренний адрес `*.railway.internal`
   с локального компьютера недоступен.
4. Выполните `python -m flask --app run db upgrade`, затем `python -m flask --app run db-check`
   в окружении с доступом к базе. В Railway миграции должны выполняться на этапе
   запуска, а не сборки: приватная сеть недоступна во время сборки.
5. В Trello исправьте число таблиц с восьми на девять в соответствии с разделом
   2.3 утверждённого документа. Подключение Railway можно отмечать выполненным
   после успешного `db-check` именно для базы Railway.

Строки `mysql://…` автоматически преобразуются в `mysql+pymysql://…`.
Приоритет настройки: явная конфигурация приложения → `DATABASE_URL` → `MYSQL_URL`
→ локальная строка по умолчанию. Значения переменных окружения имеют приоритет
над `.env`. Эти инструкции касаются базы; публикация Flask-сервиса отдельно
потребует производственного WSGI-сервера и команды запуска.

## Миграции

Миграции сохранены в `migrations/`; начальная версия не зависит от последующих
изменений Python-моделей. Служебная таблица `alembic_version` не входит в девять
таблиц предметной области. `db upgrade` применяет только ещё не выполненные версии.

После будущего изменения моделей создайте и проверьте новую миграцию:

```powershell
python -m flask --app run db migrate -m "Describe schema change"
python -m flask --app run db upgrade
python -m flask --app run db check
```

Не используйте `db.create_all()` вместо миграций для рабочей базы.
`db downgrade base` удаляет таблицы и данные; его обратимость проверяется
автотестом только на отдельной временной базе.

## Проверки записи, чтения и целостности

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Без дополнительных настроек проверки моделей выполняются на SQLite с включёнными
внешними ключами. Для тестирования на MySQL задайте отдельную тестовую учётную
запись с правом создавать и удалять базы. Пример для локального Docker:

```powershell
$env:MYSQL_TEST_URL = 'mysql+pymysql://root:stockflow-local-root@127.0.0.1:3306'
.\.venv\Scripts\python.exe -m pytest tests -q
Remove-Item Env:MYSQL_TEST_URL
```

Тесты создают случайную базу `stockflow_test_<uuid>` и удаляют только её.
Рабочая база из `DATABASE_URL` для модельных тестов не используется. Проверяются
все девять моделей, связи, уникальность, обязательные поля, CHECK-ограничения,
серверные значения по умолчанию, пароли, исторические данные заказа, каскады,
откат неудачной транзакции и повторное применение/откат миграции.

При реализации локально прошли 84 проверки: существующие тесты приложения
и конфигурации, а также модельные тесты на SQLite и MariaDB 10.4.32 из XAMPP.
MySQL 8.4 и Railway в этой среде не запускались; команды выше позволяют
повторить проверки на целевой СУБД.

Источники: [MySQL на Railway](https://docs.railway.com/databases/mysql),
[приватная сеть и этап сборки](https://docs.railway.com/networking/private-networking/how-it-works),
[Flask-Migrate](https://flask-migrate.readthedocs.io/en/latest/).
