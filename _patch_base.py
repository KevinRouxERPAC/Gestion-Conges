p = "templates/base.html"
with open(p, "r", encoding="utf-8") as f:
    s = f.read()
old = """                    {% else %}
                    <a href="{{ url_for('salarie.accueil') }}" class="hover:bg-erpac-dark px-3 py-2 rounded-md text-sm font-medium">Mes congés</a>
                    <a href="{{ url_for('salarie.calendrier') }}" class="hover:bg-erpac-dark px-3 py-2 rounded-md text-sm font-medium">Calendrier</a>
                    {% endif %}"""
new = """                    {% elif current_user.role == 'responsable' %}
                    <a href="{{ url_for('responsable.dashboard') }}" class="hover:bg-erpac-dark px-3 py-2 rounded-md text-sm font-medium">Tableau de bord</a>
                    {% else %}
                    <a href="{{ url_for('salarie.accueil') }}" class="hover:bg-erpac-dark px-3 py-2 rounded-md text-sm font-medium">Mes congés</a>
                    <a href="{{ url_for('salarie.calendrier') }}" class="hover:bg-erpac-dark px-3 py-2 rounded-md text-sm font-medium">Calendrier</a>
                    {% endif %}"""
if old in s:
    s = s.replace(old, new)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)
    print("OK")
else:
    print("Not found")
