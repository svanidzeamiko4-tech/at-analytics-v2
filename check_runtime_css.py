import sys, pathlib
sys.stdout.reconfigure(encoding='utf-8')
f = pathlib.Path('phase_2_dashboard/ui_theme.py').read_text(encoding='utf-8')
# find _runtime_theme_css function
start = f.find('_runtime_theme_css')
print(f[start:start+2000])
