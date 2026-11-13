require("pneuapi")
require("displaymanager")
per = peripheral.wrap("top")

-- x1 = x1 or ""
-- y1 = y1 or ""
-- z1 = z1 or ""
-- x2 = x2 or ""
-- y2 = y2 or ""
-- z2 = z2 or ""

function update_display()
    rclear()
    outnl("{"..tostring(x1)..", "..tostring(y1)..", "..tostring(z1).."}, {"..tostring(x2)..", "..tostring(y2)..", "..tostring(z2).."}")
end

-- local temp = nil

-- while not tonumber(temp) do
--     update_display()
--     out("Enter x1: ")
--     temp = read()
-- end
-- x1 = tonumber(temp)

-- temp = nil
-- while not tonumber(temp) do
--     update_display()
--     out("Enter y1: ")
--     temp = read()
-- end
-- y1 = tonumber(temp)

-- temp = nil
-- while not tonumber(temp) do
--     update_display()
--     out("Enter z1: ")
--     temp = read()
-- end
-- z1 = tonumber(temp)

-- temp = nil
-- while not tonumber(temp) do
--     update_display()
--     out("Enter x2: ")
--     temp = read()
-- end
-- x2 = tonumber(temp)

-- temp = nil
-- while not tonumber(temp) do
--     update_display()
--     out("Enter y2: ")
--     temp = read()
-- end
-- y2 = tonumber(temp)

-- temp = nil
-- while not tonumber(temp) do
--     update_display()
--     out("Enter z2: ")
--     temp = read()
-- end
-- z2 = tonumber(temp)

-- update_display()

x1 = 3
y1 = 172
z1 = 3
x2 = 5
y2 = 172
z2 = 5



area1 = {x1,y1,z1}
area2 = {x2,y2,z2}

--250000

while true do
setArea(per,area1,area2)

--debug
per.showArea()
term.write(countBlocksCondGTET(per,area1,area2,1))



while countBlocksCondGTET(per,area1,area2,1) do
setArea(per,area1,area2)
per.setAction("liquid_import")
dig(per)
while not isDone(per) do
sleep(0.1)
end
end

update_display()
sleep(0.1)
end