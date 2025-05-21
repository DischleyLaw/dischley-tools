from dischley_tools.main import app, db

with app.app_context():
    print("🔄 Resetting database...")
    db.drop_all()
    db.create_all()
    print("✅ Database reset complete.")