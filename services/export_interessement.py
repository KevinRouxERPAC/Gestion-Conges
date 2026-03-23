import io

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from services.interessement import calculer_interessement


def _style_header_xlsx(ws, row=1):
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )
    header_fill = PatternFill(start_color='008C3A', end_color='008C3A', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    for cell in ws[row]:
        cell.border = thin_border
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)


def _autosize_columns(ws, min_width=10, max_width=48):
    for col in range(1, ws.max_column + 1):
        letter = get_column_letter(col)
        max_len = 0
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=col).value
            if v is None:
                continue
            max_len = max(max_len, len(str(v)))
        ws.column_dimensions[letter].width = max(min_width, min(max_width, max_len + 2))


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
