import sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
f = pathlib.Path('phase_2_dashboard/app.py').read_text(encoding='utf-8')
print(f[:3000])
