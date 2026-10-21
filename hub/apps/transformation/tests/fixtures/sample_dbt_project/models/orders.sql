-- Sample dbt model: orders summary
with orders as (
    select * from {{ ref('stg_orders') }}
),

joined as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.amount,
        c.customer_name,
        c.customer_status
    from orders o
    left join {{ ref('customers') }} c
        on o.customer_id = c.customer_id
)

select * from joined
