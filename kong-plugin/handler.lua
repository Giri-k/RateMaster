local redis = require "resty.redis"

local TOKEN_BUCKET_SCRIPT = [[
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
local tokens_to_add = elapsed * refill_rate
tokens = math.min(capacity, tokens + tokens_to_add)
last_refill = now

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after = (1 - tokens) / refill_rate
end

redis.call('HSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('EXPIRE', key, ttl)

return {allowed, math.floor(tokens), math.ceil(retry_after)}
]]

local RateMasterHandler = {
  PRIORITY = 900,
  VERSION = "1.0.0",
}

local script_sha = nil

local function get_redis_connection(conf)
  local red = redis:new()
  red:set_timeout(1000)

  local ok, err = red:connect(conf.redis_host, conf.redis_port)
  if not ok then
    return nil, err
  end

  return red
end

local function ensure_script(red)
  if script_sha then
    return script_sha
  end

  local sha, err = red:script("LOAD", TOKEN_BUCKET_SCRIPT)
  if not sha then
    return nil, err
  end

  script_sha = sha
  return sha
end

local function get_identifier(conf)
  local identifier = kong.request.get_header(conf.identifier_header)
  if identifier then
    return identifier
  end

  local forwarded = kong.client.get_forwarded_ip()
  if forwarded then
    return forwarded
  end

  return kong.client.get_ip()
end

function RateMasterHandler:access(conf)
  local red, err = get_redis_connection(conf)
  if not red then
    kong.log.warn("Redis connection failed, failing open: ", err)
    return
  end

  local sha, err = ensure_script(red)
  if not sha then
    kong.log.warn("Script load failed, failing open: ", err)
    return
  end

  local identifier = get_identifier(conf)
  local key = "ratelimit:kong:" .. identifier
  local now = ngx.now()
  local capacity = conf.burst_capacity
  local refill_rate = conf.limit_per_second
  local ttl = math.ceil(capacity / refill_rate) * 2

  local result, err = red:evalsha(sha, 1, key, capacity, refill_rate, now, ttl)
  if not result then
    kong.log.warn("EVALSHA failed, failing open: ", err)
    return
  end

  local allowed = result[1]
  local remaining = result[2]
  local retry_after = result[3]

  red:set_keepalive(10000, 100)

  if allowed == 0 then
    return kong.response.exit(429, {
      error = "rate_limit_exceeded",
      retry_after = retry_after,
    }, {
      ["Retry-After"] = tostring(retry_after),
      ["X-RateLimit-Limit"] = tostring(capacity),
      ["X-RateLimit-Remaining"] = "0",
    })
  end

  kong.service.request.set_header("X-RateLimit-Remaining", tostring(remaining))
  kong.service.request.set_header("X-RateLimit-Limit", tostring(capacity))
end

return RateMasterHandler
