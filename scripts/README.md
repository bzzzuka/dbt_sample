# scripts — запуск проекта

```
scripts/
├── common.ps1      # Windows helpers
├── common.sh       # Linux/macOS helpers
├── windows/
│   ├── start-all.ps1
│   ├── start-airflow.ps1
│   ├── start-superset.ps1
│   └── stop.ps1
└── linux/
    ├── start-all.sh
    ├── start-airflow.sh
    ├── start-superset.sh
    └── stop.sh
```

Windows:

```powershell
.\scripts\windows\start-all.ps1
```

Linux/macOS:

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
```

Скрипты сами находят корень проекта и запускают `docker compose`.
На Apple Silicon при проблемах с arm64:

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```
