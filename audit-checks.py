"""Offline audit checks against preserved server files; never opens a serial port."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import types

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.modules['serial'] = types.SimpleNamespace(Serial=object)
spec = importlib.util.spec_from_file_location('audited_api', ROOT / 'audit-source/ais-energy/fcn300_api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
results = {}

hashes = json.loads((ROOT / 'audit-evidence/server-sha256.json').read_text())
for remote, expected in hashes.items():
    local = ROOT / 'audit-source' / remote.removeprefix('/home/ais/')
    assert hashlib.sha256(local.read_bytes()).hexdigest() == expected, remote
results['source_hashes_match_server'] = len(hashes)

api._cache_data.update(serial_ok=True)
api._validated.update(values={'current_a': 7.2}, timestamp='2000-01-01T00:00:00', ok=True)
body = json.loads(b''.join(api.application({'PATH_INFO': '/health'}, lambda *a: None)))
assert body['serial_ok'] is True
results['old_validated_timestamp_still_healthy'] = body

class StopAudit(BaseException):
    pass

api._raw_words.update({'0x0210': 16023, 'timestamp': '2000-01-01T00:00:00', 'serial_ok': True})
api.serial.Serial = lambda *a, **kw: types.SimpleNamespace(is_open=True)
api.serial.PARITY_NONE = 'N'
api.read_reg = lambda ser, addr, func=3: None if addr == 0x0210 else 0
api.read_regs = lambda ser, addr, count, func=3: None if addr == 0x0210 else [0] * count
real_time = api.time
def stop_at_end(seconds):
    if seconds == 0.5:
        raise StopAudit()
api.time = types.SimpleNamespace(sleep=stop_at_end, time=lambda: 0)
try:
    api.poller_loop()
except StopAudit:
    pass
assert api._raw_words['0x0210'] == 16023
assert api._raw_words['timestamp'] != '2000-01-01T00:00:00'
assert api._raw_words['serial_ok'] is False
results['failed_raw_word_retained_with_new_timestamp'] = True

api._raw_words['serial_ok'] = True
def crash():
    raise RuntimeError('offline audit injected poller failure')
api.poller_loop = crash
api.logging.exception = lambda *a, **kw: None
api.time.sleep = lambda _: (_ for _ in ()).throw(StopAudit())
try:
    api.poller_supervisor()
except StopAudit:
    pass
assert api._validated['ok'] is False
assert api._raw_words['serial_ok'] is True
results['supervisor_invalidates_vi_but_not_raw_health'] = True
api.time = real_time

bulks, singles = api._diag_windows()
results['diagnostic_windows'] = [[hex(a), n] for a, n in bulks]
results['diagnostic_single_count'] = len(singles)
results['programmed_success_cycle_sleep_seconds'] = round(5*.06 + sum(.06+.01*n for _, n, _ in api.VI_BLOCKS) + sum(.06+.01*n for _, n in bulks) + len(singles)*.06 + .5, 3)

runtime = json.loads((ROOT / 'audit-evidence/runtime.json').read_text())
prod = runtime['endpoints']['http://127.0.0.1:8080/']['body']
raw = runtime['endpoints']['http://127.0.0.1:8080/diag/raw']['body']['raw']
results['vi_apparent_power_arithmetic_anchor_kva'] = sum(prod[f'voltage_l{i}']*prod[f'current_{phase}'] for i, phase in enumerate('abc', 1))/1000
energy_rows = list(csv.DictReader((ROOT/'audit-source/fcn300-diagnostics/evidence/energy-watch.csv').open()))
energy_keys = [f'0x{a:04X}' for a in range(0x210,0x218)]
historical = json.loads((ROOT/'audit-evidence/tmp/e2a.json').read_text())
assert all(int(r[k]) == raw[k] == historical['raw'][k] for r in energy_rows for k in energy_keys)
results['identical_energy_words'] = {'watch_samples':len(energy_rows), 'watch_start':energy_rows[0]['timestamp'], 'watch_end':energy_rows[-1]['timestamp'], 'older_snapshot':historical['timestamp'], 'fresh_snapshot':runtime['captured_at']}
results['energy_cluster_be_float32_alternative_unproven'] = [struct.unpack('>f', struct.pack('>HH',raw[f'0x{a:04X}'],raw[f'0x{a+1:04X}']))[0] for a in range(0x210,0x218,2)]

rows = list(csv.DictReader((ROOT/'audit-source/fcn300-diagnostics/data/register-observations.csv').open()))
errors = []
for line, r in enumerate(rows, 2):
    if r['raw_word_1'] and r['raw_word_2']:
        u = (int(r['raw_word_1']) << 16) | int(r['raw_word_2'])
        if r['raw_bytes'] and r['raw_bytes'].upper() != f'{u:08X}':
            errors.append({'line':line,'kind':'raw_hex_mismatch','stored':r['raw_bytes'],'from_words':f'{u:08X}'})
        description = r['interpretation']
        divisor = 1790 if '/1790' in description else 10000 if '/10000' in description else 1e6 if '/1e6' in description else None
        if divisor:
            if 'CDAB' in description:
                u = (int(r['raw_word_2']) << 16) | int(r['raw_word_1'])
            value = u - 2**32 if 'i32' in description and u >= 2**31 else u
            expected = value / divisor
            if abs(expected - float(r['decoded_value'])) > .011:
                errors.append({'line':line,'kind':'decode_mismatch','stored':r['decoded_value'],'from_words':expected})
results['observation_csv_inconsistencies'] = errors
out = ROOT/'audit-evidence/offline-check-results.json'
out.write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(results, indent=2))
