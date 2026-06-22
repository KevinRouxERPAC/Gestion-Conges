import io

from openpyxl import Workbook
from openpyxl.styles import Font

from services.interessement import calculer_interessement
from services.export_utils import (
    autosize_columns as _autosize_columns,
    style_header_xlsx as _style_header_xlsx,
)


def export_interessement_xlsx(periode, include_inactifs: bool = False) -> io.BytesIO:
    res = calculer_interessement(periode, include_inactifs=include_inactifs)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Synthese'
    ws_d = wb.create_sheet('Detail')

    title = f'Interessement - {periode.libelle} ({periode.date_debut} au {periode.date_fin})'
    for w in (ws, ws_d):
        w.append([title])
        w.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
        w['A1'].font = Font(bold=True, size=13)
        w.append([])

    headers = ['Salarie', 'Actif', 'Base', 'Jours abs.', 'Malus total', 'Points final']
    ws.append(headers)
    _style_header_xlsx(ws, ws.max_row)

    for r in res:
        ws.append([
            f'{r.prenom} {r.nom}',
            'Oui' if r.actif else 'Non',
            r.base_points,
            r.total_jours_absence,
            round(r.total_malus, 2),
            round(r.points_final, 2),
        ])

    headers_d = ['Salarie', 'Type absence', 'Jours', 'Points/jour', 'Impact']
    ws_d.append(headers_d)
    _style_header_xlsx(ws_d, ws_d.max_row)

    for r in res:
        nom = f'{r.prenom} {r.nom}'
        if not r.details:
            ws_d.append([nom, '', 0, 0, 0])
            continue
        for i, d in enumerate(r.details):
            ws_d.append([
                nom if i == 0 else '',
                d.type_absence,
                d.jours,
                d.points_par_jour,
                round(d.impact_points, 2),
            ])

    _autosize_columns(ws)
    _autosize_columns(ws_d)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
