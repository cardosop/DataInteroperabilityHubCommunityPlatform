-- Sample dbt model: staging customers
with source as (
    select * from {{ source('raw', 'customers') }}
),

cleaned as (
    select
        id as customer_id,
        trim(upper(name)) as customer_name,
        email,
        signup_date,
        case
            when status is null then 'unknown'
            else status
        end as customer_status
    from source
)

select * from cleaned
