.PHONY: up down build logs migrate makemigrations test lint fmt shell

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec core-api python manage.py migrate

makemigrations:
	docker compose exec core-api python manage.py makemigrations

test:
	docker compose exec core-api pytest --cov=apps -q
	docker compose exec notification-service pytest -q

lint:
	pre-commit run --all-files

fmt:
	black services
	isort services

shell:
	docker compose exec core-api python manage.py shell
