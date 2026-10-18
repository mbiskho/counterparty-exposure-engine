from __future__ import annotations

from html import escape

from .models import ExposureReport


def _label(value: str) -> str:
    return escape(value, quote=True)


def _money(value: float, currency: str) -> str:
    return f"{'-' if value < 0 else ''}{currency} {abs(value):,.0f}"


def render_project_screenshot(report: ExposureReport) -> str:
    counterparties = sorted(
        report.counterparties.values(),
        key=lambda item: item.current_exposure,
        reverse=True,
    )
    if not counterparties:
        raise ValueError("report must contain counterparty results")
    width, height = 1200, 820
    chart_left, chart_right, chart_top = 350, 900, 456
    row_height = 42
    max_exposure_or_limit = max(
        max(item.current_exposure for item in counterparties),
        max(item.limit for item in counterparties),
    )
    scale = (chart_right - chart_left) / max(max_exposure_or_limit, 1.0)
    total_exposure = sum(item.current_exposure for item in counterparties)
    total_pfe = sum(item.pfe for item in counterparties)
    breached = sum(item.limit_breached for item in counterparties)
    content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="chart-title chart-description">',
        '<title id="chart-title">Counterparty Exposure Engine project overview</title>',
        (
            '<desc id="chart-description">White project overview and current '
            f"exposure chart for {len(counterparties)} counterparties. "
            f"Total current exposure: {_label(_money(total_exposure, report.currency))}."
            "</desc>"
        ),
        '<rect width="1200" height="820" fill="#ffffff"/>',
        '<rect x="34" y="30" width="1132" height="760" rx="24" fill="#ffffff" stroke="#e5eaf1" stroke-width="2"/>',
        '<rect x="66" y="64" width="48" height="48" rx="14" fill="#eaf2ff"/>',
        '<path d="M78 98V82h7v16m5 0V74h7v24m5 0V87h7v11" fill="none" stroke="#2563eb" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
        '<text x="130" y="84" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.5">QUANT ANALYSIS • COUNTERPARTY RISK</text>',
        '<text x="130" y="111" fill="#0f172a" font-family="Inter,Arial,sans-serif" font-size="25" font-weight="700">Counterparty Exposure Engine</text>',
        '<text x="66" y="168" fill="#0f172a" font-family="Inter,Arial,sans-serif" font-size="30" font-weight="700">Know where exposure sits before limits are hit.</text>',
        '<text x="66" y="199" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="16">Netting-aware current exposure, haircut-adjusted collateral, PFE add-ons, and limit monitoring.</text>',
    ]
    metrics = [
        ("CURRENT EXPOSURE", _money(total_exposure, report.currency), "#1d4ed8"),
        ("PFE ESTIMATE", _money(total_pfe, report.currency), "#7c3aed"),
        ("LIMIT BREACHES", str(breached), "#b91c1c" if breached else "#15803d"),
    ]
    for index, (heading, value, color) in enumerate(metrics):
        x = 66 + index * 356
        content.extend(
            [
                f'<rect x="{x}" y="230" width="332" height="94" rx="16" fill="#f8fafc" stroke="#e2e8f0"/>',
                f'<text x="{x + 20}" y="260" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="11" font-weight="700" letter-spacing="1.1">{heading}</text>',
                f'<text x="{x + 20}" y="298" fill="{color}" font-family="Inter,Arial,sans-serif" font-size="23" font-weight="700">{_label(value)}</text>',
            ]
        )
    content.extend(
        [
            '<text x="66" y="372" fill="#0f172a" font-family="Inter,Arial,sans-serif" font-size="20" font-weight="700">Current exposure by counterparty</text>',
            '<text x="66" y="397" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="13">Bar = current exposure • Marker = approved limit</text>',
        ]
    )
    for index, item in enumerate(counterparties):
        y = chart_top + index * row_height
        bar_width = item.current_exposure * scale
        limit_x = chart_left + item.limit * scale
        color = "#dc2626" if item.limit_breached else "#2563eb"
        content.extend(
            [
                f'<text x="80" y="{y + 5}" fill="#334155" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="700">{_label(item.counterparty)}</text>',
                f'<rect x="{chart_left}" y="{y - 9}" width="{chart_right - chart_left}" height="18" rx="6" fill="#f1f5f9"/>',
                f'<rect x="{chart_left}" y="{y - 9}" width="{bar_width:.2f}" height="18" rx="6" fill="{color}"><title>Current exposure: {_label(_money(item.current_exposure, report.currency))}</title></rect>',
                f'<line x1="{limit_x:.2f}" y1="{y - 14}" x2="{limit_x:.2f}" y2="{y + 14}" stroke="#0f172a" stroke-width="2"><title>Limit: {_label(_money(item.limit, report.currency))}</title></line>',
                f'<text x="1110" y="{y + 5}" text-anchor="end" fill="{color}" font-family="Inter,Arial,sans-serif" font-size="12" font-weight="700">{_label(_money(item.current_exposure, report.currency))}</text>',
            ]
        )
    footer_y = chart_top + row_height * len(counterparties) + 40
    content.extend(
        [
            f'<line x1="66" y1="{footer_y - 18}" x2="1134" y2="{footer_y - 18}" stroke="#e2e8f0"/>',
            f'<text x="66" y="{footer_y + 5}" fill="#94a3b8" font-family="Inter,Arial,sans-serif" font-size="12">Illustrative notional add-on • Exposure netted only within each netting set • Synthetic data</text>',
            "</svg>",
        ]
    )
    return "\n".join(content)


def render_flow_screenshot(report: ExposureReport) -> str:
    sets = sorted(
        report.netting_sets,
        key=lambda item: item.current_exposure,
        reverse=True,
    )
    if not sets:
        raise ValueError("report must contain netting-set results")
    width, height = 1200, 820
    chart_left, chart_right, chart_top = 360, 900, 528
    row_height = 42
    max_exposure = max(item.current_exposure for item in sets)
    scale = (chart_right - chart_left) / max(max_exposure, 1.0)
    steps = [
        ("01", "Trades", ("Counterparty", "netting set, MTM", "notional and PFE rate")),
        ("02", "Net MTM", ("Offset trade values", "inside each legal", "netting set only")),
        ("03", "Collateral", ("Apply haircut to", "eligible collateral", "value")),
        ("04", "Exposure", ("Floor net MTM less", "collateral at zero")),
        ("05", "Monitor", ("Add PFE estimate", "and check limits")),
    ]
    content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="chart-title chart-description">',
        '<title id="chart-title">Counterparty exposure workflow</title>',
        (
            '<desc id="chart-description">White workflow diagram from trade '
            'inputs through netting, collateral, exposure and limit monitoring, '
            "with current exposure chart by netting set.</desc>"
        ),
        '<rect width="1200" height="820" fill="#ffffff"/>',
        '<rect x="34" y="30" width="1132" height="760" rx="24" fill="#ffffff" stroke="#e5eaf1" stroke-width="2"/>',
        '<text x="66" y="86" fill="#2563eb" font-family="Inter,Arial,sans-serif" font-size="13" font-weight="700" letter-spacing="1.5">HOW IT WORKS</text>',
        '<text x="66" y="126" fill="#0f172a" font-family="Inter,Arial,sans-serif" font-size="30" font-weight="700">From trade ledger to counterparty exposure</text>',
        '<text x="66" y="157" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="15">Netting, collateral haircuts and limit utilization stay visible at each step.</text>',
    ]
    box_y, box_width, gap = 196, 202, 22
    for index, (number, heading, detail_lines) in enumerate(steps):
        x = 66 + index * (box_width + gap)
        content.extend(
            [
                f'<rect x="{x}" y="{box_y}" width="{box_width}" height="146" rx="16" fill="#f8fafc" stroke="#dbe4ef"/>',
                f'<circle cx="{x + 28}" cy="{box_y + 31}" r="15" fill="#dbeafe"/>',
                f'<text x="{x + 28}" y="{box_y + 36}" text-anchor="middle" fill="#1d4ed8" font-family="Inter,Arial,sans-serif" font-size="11" font-weight="700">{number}</text>',
                f'<text x="{x + 18}" y="{box_y + 69}" fill="#0f172a" font-family="Inter,Arial,sans-serif" font-size="15" font-weight="700">{heading}</text>',
                f'<text x="{x + 18}" y="{box_y + 94}" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="11">',
            ]
        )
        for line_index, line in enumerate(detail_lines):
            content.append(
                f'<tspan x="{x + 18}" dy="{0 if line_index == 0 else 15}">{_label(line)}</tspan>'
            )
        content.append("</text>")
        if index < len(steps) - 1:
            content.append(
                f'<path d="M{x + box_width + 5} {box_y + 73}h12m-5 -5 5 5-5 5" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            )
    content.extend(
        [
            '<text x="66" y="398" fill="#0f172a" font-family="Inter,Arial,sans-serif" font-size="20" font-weight="700">Current exposure by netting set</text>',
            '<text x="66" y="422" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="13">After eligible collateral • Within-set netting only</text>',
            '<rect x="66" y="443" width="1068" height="326" rx="16" fill="#fbfdff" stroke="#e2e8f0"/>',
            '<text x="82" y="472" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="11">COUNTERPARTY / NETTING SET</text>',
            '<text x="360" y="472" fill="#64748b" font-family="Inter,Arial,sans-serif" font-size="11">CURRENT EXPOSURE</text>',
        ]
    )
    for index, item in enumerate(sets):
        y = chart_top + index * row_height
        bar_width = item.current_exposure * scale
        label = f"{item.counterparty} / {item.netting_set}"
        content.extend(
            [
                f'<text x="82" y="{y + 4}" fill="#334155" font-family="Inter,Arial,sans-serif" font-size="11" font-weight="600">{_label(label)}</text>',
                f'<rect x="{chart_left}" y="{y - 7}" width="{chart_right - chart_left}" height="13" rx="5" fill="#f1f5f9"/>',
                f'<rect x="{chart_left}" y="{y - 7}" width="{bar_width:.2f}" height="13" rx="5" fill="#2563eb"><title>{_label(_money(item.current_exposure, report.currency))}</title></rect>',
                f'<text x="1110" y="{y + 4}" text-anchor="end" fill="#1d4ed8" font-family="Inter,Arial,sans-serif" font-size="11" font-weight="700">{_label(_money(item.current_exposure, report.currency))}</text>',
            ]
        )
    content.extend(
        [
            '<text x="82" y="758" fill="#94a3b8" font-family="Inter,Arial,sans-serif" font-size="11">PFE = current exposure + illustrative notional-based add-on • Not a regulatory exposure calculation</text>',
            "</svg>",
        ]
    )
    return "\n".join(content)
