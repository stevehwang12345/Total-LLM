#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 초기화 스크립트
"""

import asyncio
import sys
from pathlib import Path
import asyncpg
import yaml

# 프로젝트 루트 경로 추가


async def init_database():
    """
    데이터베이스 연결 및 스키마 생성
    """
    # Config 로드
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    db_config = config['database']

    print("=" * 60)
    print("🗄️  PostgreSQL Database Initialization")
    print("=" * 60)

    try:
        # 1. postgres 데이터베이스에 연결 (데이터베이스 생성용)
        print(f"\n1. Connecting to PostgreSQL...")
        conn = await asyncpg.connect(
            host=db_config['host'],
            port=db_config['port'],
            user='postgres',  # 기본 관리자 계정
            password=input("Enter postgres password: "),  # 보안을 위해 입력 요청
            database='postgres'
        )

        # 2. 데이터베이스 생성 (이미 존재하면 스킵)
        print(f"\n2. Creating database: {db_config['database']}")
        await conn.execute(f'''
            SELECT 'CREATE DATABASE {db_config["database"]}'
            WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{db_config["database"]}')
        ''')

        # 3. 사용자 생성 (이미 존재하면 스킵)
        print(f"\n3. Creating user: {db_config['username']}")
        try:
            await conn.execute(f'''
                CREATE USER {db_config["username"]} WITH PASSWORD '{db_config["password"]}'
            ''')
        except asyncpg.exceptions.DuplicateObjectError:
            print(f"   ⚠️  User {db_config['username']} already exists")

        # 4. 권한 부여
        print(f"\n4. Granting privileges...")
        await conn.execute(f'''
            GRANT ALL PRIVILEGES ON DATABASE {db_config["database"]} TO {db_config["username"]}
        ''')

        await conn.close()

        # 5. 새 데이터베이스에 연결하여 스키마 생성
        print(f"\n5. Connecting to {db_config['database']} database...")
        conn = await asyncpg.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
            database=db_config['database']
        )

        # 6. 스키마 SQL 파일 읽기 및 실행
        print(f"\n6. Creating schema...")
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            schema_sql = f.read()

        await conn.execute(schema_sql)

        # 7. 테이블 확인
        print(f"\n7. Verifying tables...")
        tables = await conn.fetch('''
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        ''')

        print(f"\n   ✅ Created {len(tables)} tables:")
        for table in tables:
            row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table['tablename']}")
            print(f"      - {table['tablename']}: {row_count} rows")

        await conn.close()

        print("\n" + "=" * 60)
        print("✅ Database initialization completed!")
        print("=" * 60)
        print(f"\nConnection info:")
        print(f"  Host: {db_config['host']}:{db_config['port']}")
        print(f"  Database: {db_config['database']}")
        print(f"  User: {db_config['username']}")
        print(f"\nTest connection:")
        print(f"  psql -h {db_config['host']} -U {db_config['username']} -d {db_config['database']}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_database())
