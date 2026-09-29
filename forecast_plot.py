"""A two-day, phone-readable forecast card rendered entirely with Matplotlib."""
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TZ = ZoneInfo('Australia/Sydney')
INK = '#172f40'
MUTED = '#647987'
TEAL = '#007f7d'
BLUE = '#6893ad'
BG = '#f4f7fa'
COMPASS = np.array(['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'])
HEIGHT_BINS = ((0, 1, '0-1ft'), (1, 2, '1-2ft'), (2, 3, '2-3ft'), (3, 4, '3-4ft'),
               (4, 5, '4-5ft'), (5, 6, '5-6ft'), (6, 8, '6-8ft'), (8, 10, '8-10ft'),
               (10, 12, '10-12ft'))


def compass_name(degrees):
    return COMPASS[int(np.floor((degrees % 360) / 22.5 + .5)) % 16]


def compass_arrow(ax, x, y, direction, color=INK):
    """North-up source bearing; arrowhead points toward the FROM direction."""
    angle = np.deg2rad(direction)
    dx, dy = np.sin(angle) * .016, np.cos(angle) * .18
    ax.annotate('', xy=(x + dx, y + dy), xytext=(x - dx, y - dy),
                xycoords='axes fraction', textcoords='axes fraction',
                arrowprops={'arrowstyle':'-|>', 'lw':1.5, 'color':color, 'mutation_scale':11})


def surf_height_band(value_ft):
    for low, high, label in HEIGHT_BINS:
        if low <= value_ft < high:
            return label
    return '12ft+'


def daylight_means(frame, start):
    result = []
    for offset in (0, 1):
        day_start = start + pd.Timedelta(days=offset)
        day_end = day_start + pd.Timedelta(days=1)
        block = frame.loc[(frame.index >= day_start) & (frame.index < day_end)]
        local_hours = block.index.tz_convert(TZ).hour
        result.append((block.loc[(local_hours >= 6) & (local_hours < 12)].nearshore_height_ft.mean(),
                       block.loc[(local_hours >= 12) & (local_hours < 18)].nearshore_height_ft.mean()))
    return result


def render_forecast(frame, tide=None, events=None, output=None):
    t = frame.index.tz_convert(TZ)
    start, end = frame.index[0], frame.index[-1]
    run = pd.Timestamp(frame.attrs['run_utc'])
    samples = frame.iloc[::2].iloc[:-1]  # Six-hour markers, never interpolated.
    tick_times = samples.index.tz_convert(TZ)
    x_ticks = mdates.date2num(tick_times)
    left, right = .085, .965

    with plt.rc_context({'font.family':'DejaVu Sans', 'font.size':12,
                         'text.color':INK, 'axes.labelcolor':MUTED}):
        fig = plt.figure(figsize=(6, 7.5), dpi=180, facecolor=BG)
        fig.text(.045, .957, 'SURF FORECAST', fontsize=23, weight='bold')
        fig.text(.965, .963, '48 HOURS', fontsize=12, weight='bold', ha='right', color=TEAL)
        model = str(frame.attrs.get('model', frame.attrs.get('source', 'ECMWF'))).upper()
        fig.text(.045, .924, f'{model}  {run:%d %b %Y} / {run:%H} UTC', fontsize=11.5, color=MUTED)
        fig.text(.965, .924, 'Local time: Sydney', fontsize=11.5, ha='right', color=MUTED)

        # Two real 24-hour windows, shown explicitly to avoid implying calendar-day extrema.
        for day, x in enumerate([.045, .525]):
            boundary = start + pd.Timedelta(hours=24 * day)
            block = frame.loc[(frame.index >= boundary) & (frame.index < boundary + pd.Timedelta(hours=24))]
            local = boundary.tz_convert(TZ)
            finish = (boundary + pd.Timedelta(hours=24)).tz_convert(TZ)
            patch = FancyBboxPatch((x, .809), .43, .095, boxstyle='round,pad=.008,rounding_size=.01',
                                  linewidth=0, facecolor='white', transform=fig.transFigure, zorder=-1)
            fig.add_artist(patch)
            fig.text(x + .018, .879, f'{local:%a %d %b}'.upper(), fontsize=13, weight='bold')
            am, pm = daylight_means(frame, boundary)[day]
            fig.text(x + .018, .849, f'AM {surf_height_band(am)}', fontsize=15, weight='bold', color=TEAL)
            fig.text(x + .018, .821, f'PM {surf_height_band(pm)}', fontsize=15, weight='bold', color=TEAL)
            fig.text(x + .34, .841, 'ft', fontsize=15, color=TEAL)
            fig.text(x + .018, .804, f'{local:%H:%M} → {finish:%a %H:%M}', fontsize=9.5, color=MUTED)

        fig.text(.045, .780, 'WAVE HEIGHT', fontsize=13, weight='bold')
        fig.text(.48, .780, 'Nearshore', fontsize=11.5, color=TEAL, weight='bold')
        fig.text(.735, .780, '- - Offshore', fontsize=11.5, color=BLUE)
        wave_ax = fig.add_axes([left, .635, right-left, .126])
        wind_ax = fig.add_axes([left, .265, right-left, .09])
        tide_ax = fig.add_axes([left, .105, right-left, .085])

        def style_axis(ax, ticks=False):
            ax.set_facecolor('white')
            ax.set_xlim(t[0], t[-1])
            ax.set_xticks(x_ticks)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=TZ))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=3, min_n_ticks=2))
            ax.tick_params(axis='both', length=0, labelsize=11, colors=MUTED)
            ax.tick_params(axis='x', labelbottom=ticks, pad=5)
            ax.grid(axis='y', color='#e2e9ef', lw=.7)
            ax.grid(axis='x', color='#eef2f5', lw=.65)
            ax.set_axisbelow(True)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.axvline(start + pd.Timedelta(hours=24), color='#c6d4df', lw=1.1)
            # Nighttime shading: the clock is local, including daylight-saving changes.
            dates = pd.date_range(t[0].normalize() - pd.Timedelta(days=1), t[-1].normalize(), freq='D')
            for date in dates:
                a = date + pd.DateOffset(hours=19)
                b = date + pd.DateOffset(days=1, hours=6)
                ax.axvspan(a, b, color='#e8edf3', alpha=.6, zorder=0)

        for ax in [wave_ax, wind_ax, tide_ax]:
            style_axis(ax, ticks=True)
        wave_ax.bar(t[:-1], frame.nearshore_height_ft.iloc[:-1], width=2.5/24,
                    align='edge', color=TEAL, alpha=.19, linewidth=0)
        wave_ax.plot(t, frame.nearshore_height_ft, color=TEAL, lw=2.1)
        wave_ax.plot(t, frame.offshore_height_ft, color=BLUE, lw=1.5, ls=(0,(3,2)))
        wave_ax.set_ylim(0, max(frame.nearshore_height_ft.max(), frame.offshore_height_ft.max()) * 1.15)

        fig.text(.045, .581, 'OFFSHORE / peak period + direction', fontsize=12.5, weight='bold')
        direction_ax = fig.add_axes([left, .510, right-left, .06])
        direction_ax.set_axis_off()
        # Use centres of the eight six-hour columns for legible source bearings.
        for j, (_, row) in enumerate(samples.iterrows()):
            x = (j + .5) / len(samples)
            compass_arrow(direction_ax, x, .65, row.wave_direction_deg, TEAL)
            direction_ax.text(x, .03, f'{row.peak_period_s:.0f}s {compass_name(row.wave_direction_deg)}',
                              ha='center', va='bottom', fontsize=11, color=INK)
        fig.text(.045, .493, 'Combined waves; arrows point to the source.', fontsize=10.5, color=MUTED)

        swell_columns = ['primary_swell_height_m', 'primary_swell_period_s', 'primary_swell_direction_deg',
                         'secondary_swell_height_m', 'secondary_swell_period_s', 'secondary_swell_direction_deg']
        swell_available = all(c in frame and frame[c].notna().any() for c in swell_columns)
        wind_title_y = .365
        wind_y = .265
        tide_title_y = .208
        tide_y = .105
        if swell_available:
            for x, title, prefix in [(.045, 'PRIMARY SWELL', 'primary_swell'), (.525, 'SECONDARY SWELL', 'secondary_swell')]:
                fig.add_artist(FancyBboxPatch((x, .407), .43, .067,
                               boxstyle='round,pad=.008,rounding_size=.008', linewidth=0,
                               facecolor='#e8eef3', transform=fig.transFigure, zorder=-1))
                row = frame.iloc[len(frame)//2]
                fig.text(x + .018, .450, title, fontsize=11.5, weight='bold', color=MUTED)
                fig.text(x + .018, .423, f"{row[prefix+'_height_m']*3.28084:.1f}ft  {row[prefix+'_period_s']:.0f}s  {compass_name(row[prefix+'_direction_deg'])}", fontsize=13, weight='bold', color=INK)
            fig.text(.5, .388, 'Primary and secondary swell trains', ha='center', fontsize=10.5, color=MUTED)
        else:
            wind_title_y, wind_y, tide_title_y, tide_y = .425, .325, .268, .165

        fig.text(.045, wind_title_y, 'WIND / kn', fontsize=13, weight='bold')
        wind_ax.set_position([left, wind_y, right-left, .09])
        wind_ax.plot(t, frame.wind_speed_kn, color='#3e70a0', lw=1.8)
        wind_ax.fill_between(t, frame.wind_speed_kn, color='#3e70a0', alpha=.1)
        wind_ax.set_ylim(0, max(8, frame.wind_speed_kn.max()*1.7))
        for timestamp, row in samples.iterrows():
            wind_ax.text(timestamp, .88, compass_name(row.wind_direction_deg),
                         transform=wind_ax.get_xaxis_transform(), ha='center', va='center', fontsize=10.5, color='#3e70a0')

        fig.text(.045, tide_title_y, 'TIDE / m LAT', fontsize=13, weight='bold')
        tide_ax.set_position([left, tide_y, right-left, .085])
        if tide is not None:
            tide_ax.plot(tide.index.tz_convert(TZ), tide, color='#74679b', lw=1.9)
            tide_ax.fill_between(tide.index.tz_convert(TZ), tide, color='#74679b', alpha=.08)
            shown = events.loc[start:end]
            tide_ax.scatter(shown.index.tz_convert(TZ), shown.height_m, color='#74679b', s=17, zorder=3)
            tide_ax.set_ylim(0, max(1, tide.max()*1.1))
        else:
            tide_ax.text(.5, .5, 'BOM tide data unavailable', ha='center', transform=tide_ax.transAxes, fontsize=12, color=MUTED)

        fig.text(.045, .052, f'{t[0]:%d %b %H:%M} - {t[-1]:%d %b %H:%M}', fontsize=10.5, color=MUTED)
        fig.text(.965, .052, 'BOM*', ha='right', fontsize=10.5, color=MUTED)
        if output is not None:
            output = Path(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output, dpi=180, facecolor=BG)
        return fig
