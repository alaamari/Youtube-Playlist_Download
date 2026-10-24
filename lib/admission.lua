-- One atomic reservation across every server instance. Never refund a provisioned session.
local now=tonumber(ARGV[2])
local window=tonumber(ARGV[3])
local lease=tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE',KEYS[2],'-inf',now-window)
redis.call('ZREMRANGEBYSCORE',KEYS[3],'-inf',now-86400000)
if redis.call('EXISTS',KEYS[1])==1 then return {0,1,redis.call('PTTL',KEYS[1])} end
if redis.call('ZCARD',KEYS[2])>=tonumber(ARGV[5]) then
 local oldest=redis.call('ZRANGE',KEYS[2],0,0,'WITHSCORES')
 return {0,2,tonumber(oldest[2])+window-now}
end
if redis.call('ZCARD',KEYS[3])>=tonumber(ARGV[6]) then
 local oldest=redis.call('ZRANGE',KEYS[3],0,0,'WITHSCORES')
 return {0,3,tonumber(oldest[2])+86400000-now}
end
redis.call('SET',KEYS[1],ARGV[1],'PX',lease)
redis.call('ZADD',KEYS[2],now,ARGV[1])
redis.call('PEXPIRE',KEYS[2],window+86400000)
redis.call('ZADD',KEYS[3],now,ARGV[1])
redis.call('PEXPIRE',KEYS[3],172800000)
return {1,tonumber(ARGV[5])-redis.call('ZCARD',KEYS[2]),0}
