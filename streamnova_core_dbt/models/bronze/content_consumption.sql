{{
    config(
        materialized='table',
        schema='bronze'
    )
}}

SELECT
    *
FROM
    {{ source('source', 'content_consumption') }}