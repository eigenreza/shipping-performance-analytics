import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, CustomChart, GraphChart, LineChart, ScatterChart } from 'echarts/charts'
import { AriaComponent, GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([BarChart, CustomChart, GraphChart, LineChart, ScatterChart, AriaComponent, GridComponent, MarkLineComponent, TooltipComponent, SVGRenderer])
import { FONT, INK } from '../lib/theme'

type Props = {
  option: echarts.EChartsCoreOption
  height?: number
  onClick?: (params: echarts.ECElementEvent) => void
  ariaLabel: string
}

// Shared axis and tooltip styling: recessive grid, text in ink colors, never series colors.
export const axisStyle = {
  axisLine: { lineStyle: { color: INK.grid } },
  axisTick: { show: false },
  axisLabel: { color: INK.secondary, fontFamily: FONT },
  splitLine: { lineStyle: { color: INK.grid } },
  nameTextStyle: { color: INK.secondary, fontFamily: FONT },
}

export const tooltipStyle = {
  backgroundColor: '#ffffff',
  borderColor: INK.grid,
  textStyle: { color: INK.primary, fontFamily: FONT, fontSize: 12 },
  extraCssText: 'box-shadow: 0 4px 14px rgba(0,0,0,.08); border-radius: 6px;',
}

export default function Chart({ option, height = 320, onClick, ariaLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    chart.current = echarts.init(ref.current, undefined, { renderer: 'svg' })
    const ro = new ResizeObserver(() => chart.current?.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chart.current?.dispose()
    }
  }, [])

  useEffect(() => {
    chart.current?.setOption(
      { textStyle: { fontFamily: FONT }, animationDuration: 400, aria: { enabled: true, label: { description: ariaLabel } }, ...option },
      true,
    )
  }, [option, ariaLabel])

  useEffect(() => {
    const c = chart.current
    if (!c || !onClick) return
    c.on('click', onClick)
    return () => {
      c.off('click', onClick)
    }
  }, [onClick])

  return <div ref={ref} style={{ height, width: '100%' }} role="img" aria-label={ariaLabel} />
}
