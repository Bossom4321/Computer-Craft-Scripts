package.path = package.path .. ";.apis/?.lua"
require("rsapi")
pd = peripheral.wrap("left")
while true do
sleep(0.1)

co=sublevel.getLogicalPose().position

x1=10
x2=-10
y1=10
y2=-10
z1=10
z2=-10
pos1= {x=x1+co.x,y=y1+co.y,z=z1+co.z}
pos2= {x=x2+co.x,y=y2+co.y,z=z2+co.z}

if #(pd.getPlayersInCoords(pos1,pos2)) == 0 then
rOut("top",0)
else
rOut("top",15)
end
end

