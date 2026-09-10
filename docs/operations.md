# Safe operations

All commands below are read-only. Supply SSH credentials locally; none are stored in this repository.

```sh
ssh ais@100.73.124.7
systemctl --user is-active ais-energy.service fcn300-dashboard.service
ps -ef | grep -E 'fcn300_api|fcn300-diagnostics/app.py' | grep -v grep
fuser /dev/ttyUSB0
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/diag/raw
curl -fsS http://127.0.0.1:8090/healthz
curl -fsS http://127.0.0.1:3000/water_monitoring?select=id\&limit=1
sudo -u postgres pg_isready -h 127.0.0.1 -p 5432
sha256sum /home/ais/ais-energy/fcn300_api.py /home/ais/ais-energy/fcn300_reader.py
sha256sum /home/ais/fcn300-diagnostics/app.py /home/ais/fcn300-diagnostics/static/*
ss -ltnp | grep -E ':8080|:8090|:3000'
```

If `/dev/ttyUSB0` has more than one owner, stop and investigate; do not start another serial client.

Both production applications are enabled user services and user `ais` has lingering enabled. The legacy OMP `diag` process was retired after the systemd dashboard cutover.
