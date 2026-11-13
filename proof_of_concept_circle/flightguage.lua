package.path = package.path .. ";.apis/?.lua"
require("utils")
require("displaymanager")


function drawline(xpos,ypos,xpos2,ypos2)
    for j=xpos,xpos2,0.15 do
    local sl = slope(xpos,ypos,xpos2,ypos2)
    per.setCursorPos(j,sl*(j-xpos)+ypos)
    per.blit("-","F","0")
end
    
end

--term.write(sizeX(term).." "..sizeY(term))
per = peripheral.wrap("top")
per.setTextScale(0.5)
--35,16
x=sizeX(per)/2
y=sizeY(per)/2


for b=1,10 do
for z =0,1,0.01 do
rclear(per)
per.setCursorPos(x,y)
out(" ",per,"white","white")
nx,ny,sx,sy = tracecircumfrence(x,y,25,z)
nx2,ny2,sx2,sy2 = tracecircumfrence(x,y,25+40,z)

drawline(nx,ny,nx2,ny2)
drawline(sx2,sy2,sx,sy)

per.setCursorPos(nx2,ny2)
per.blit("x","0","F")
per.setCursorPos(sx2,sy2)
per.blit("x","0","F")

per.setCursorPos(nx,ny)
per.blit("x","0","F")
per.setCursorPos(sx,sy)
per.blit("x","0","F")
sleep(0.1)
end
end
-- term.setCursorPos(sx,sy)
-- term.blit("X","0","F")

