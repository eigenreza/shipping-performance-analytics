-- Calendar from the first MRV reporting year to the data end date.
select
    cast(strftime(d, '%Y%m%d') as integer) as date_id,
    cast(d as date) as date_key,
    year(d) as year,
    quarter(d) as quarter,
    month(d) as month,
    strftime(d, '%b') as month_short,
    strftime(d, '%Y-%m') as year_month,
    'Q' || quarter(d) as quarter_label,
    isodow(d) as iso_weekday,
    strftime(d, '%a') as weekday_short,
    isodow(d) >= 6 as is_weekend,
    cast(date_trunc('month', d) as date) as month_start,
    cast(make_date(year(d), 12, 31) as date) as year_end
from range(date '2018-01-01', date '{{ var("data_end_date") }}' + interval 1 day, interval 1 day) as t(d)
