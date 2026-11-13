package.path = package.path .. ";.apis/?.lua"
require("displaymanager")
th = peripheral.wrap("left")
mon = peripheral.find("monitor")
mon.clear()
mon.setCursorPos(1, 1)
while true do
    th.resize(sizeX(mon), sizeY(mon) - 1)
    redstone.setOutput("back", true)
    sleep(0.1)
    redstone.setOutput("back", false)
    data = th.dump()
    mon.clear()
    mon.setCursorPos(1, 1)
    outnl("--Vault Contents--",mon)
    iter = 1

    z = 3
    for i = 0, #data do
        if data[i] ~= nil then
            text = (tostring(iter) .. ": ")
            out(text,mon)
            local x, y = mon.getCursorPos()
            mon.setCursorPos(6,y)
            outnl(data[i],mon)
            z = z + 1
            iter = iter + 1
        end
    end

    sleep(1)
end
