.PHONY: up seed

up:
	npm ci --prefix frontend
	npm run build --prefix frontend
	docker compose up -d --build

seed:
	COUCHDB_URL=http://127.0.0.1:5984 \
	COUCHDB_USER=admin \
	COUCHDB_PASSWORD=password \
	COUCHDB_PRODUCTS_DB=products \
	python3 backend/scripts/seed_products.py
