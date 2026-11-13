pr = peripheral.wrap("top")
while true do
pr = peripheral.wrap("top")
if pr ~= nil then
temp = false
mon = peripheral.find("monitor") or term
if peripheral.find("monitor") then
    mon.setTextScale(0.5)
end
mon.clear()
lst = peripheral.getMethods("top")
for i=1, #lst do
mon.setCursorPos(1,i)
mon.write(lst[i])
temp = pr
end
elseif (pr ~= temp) and pr ~= nil then
mon.clear()
non.setCursorPos(1,1)
end
sleep(0.1)
end

