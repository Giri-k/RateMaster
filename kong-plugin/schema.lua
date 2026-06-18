return {
  name = "ratemaster",
  fields = {
    { config = {
        type = "record",
        fields = {
          { limit_per_second = { type = "number", required = true } },
          { burst_capacity = { type = "number", required = true } },
          { redis_host = { type = "string", default = "redis" } },
          { redis_port = { type = "number", default = 6379 } },
          { identifier_header = { type = "string", default = "X-API-Key" } },
        },
      },
    },
  },
}
