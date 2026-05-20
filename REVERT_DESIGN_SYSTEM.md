# Design System — შენახვა და უკან დაბრუნება

**Commit (Modern SaaS theme):** იხილეთ `git log --oneline -1` ბოლო `design:` / `Design system` commit-ის შემდეგ.

## სრულად უკან (მხოლოდ თემა)

```powershell
cd "F:\AT Analitc Proect"
git log --oneline -5
# იპოვეთ commit SHA *წინ* design system commit-ისა (მაგ. rs.ge ან hide sidebar)

git revert <DESIGN_COMMIT_SHA> --no-edit
```

ან ერთი ნაბიჯით (თუ design commit ბოლოა):

```powershell
git revert HEAD --no-edit
```

## მხოლოდ `phase_2_dashboard` ძველ ვერსიაზე

```powershell
git checkout <PARENT_SHA> -- phase_2_dashboard/ui_theme.py phase_2_dashboard/dashboard_layout.py phase_2_dashboard/dashboard_core.py phase_2_dashboard/pages/login.py phase_2_dashboard/pages/admin_panel.py phase_2_dashboard/pages/order_planning.py phase_2_dashboard/charts/ phase_2_dashboard/store_efficiency_panel.py
```

## შედარება ორ commit-ს შორის

```powershell
git diff <PARENT_SHA> HEAD -- phase_2_dashboard/ui_theme.py
```

**შენიშვნა:** `integrations/rs_ge/` და `check_*.py` design commit-ში არ შედის (სხვა ფუნქციები).
