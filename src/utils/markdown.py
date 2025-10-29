def table_to_markdown(table_cells):
    # Convert 'cells' dict to list of rows (simple version)
    rows = []
    row_idx = 0
    while True:
        row = []
        col_idx = 0
        while True:
            key = f'{row_idx}_{col_idx}'
            if key in table_cells:
                row.append(table_cells[key]['text'].replace('\n', ' '))
                col_idx += 1
            else:
                break
        if not row:
            break
        rows.append(row)
        row_idx += 1
    # Build markdown
    md = '| ' + ' | '.join(rows[0]) + ' |\n'
    md += '| ' + ' | '.join(['---'] * len(rows[0])) + ' |\n'
    for r in rows[1:]:
        md += '| ' + ' | '.join(r) + ' |\n'
    return md
