--
--
--
--
--

 Compass = 0
 Xpos = 0
 Ypos = 0
 Zpos = 0
 Laststepx = 0
 Laststepz = 0
 Laststepcard = 3
 Laststep = 1

function db()
    if debu == true then
        term.clear()
        term.write("Last rel Coords: ")
        term.write(Xpos)
        term.write(" ")
        term.write(Ypos)
        term.write(" ")
        term.write(Zpos)
        term.setCursorPos(1,2)
        term.write("LastStep: ")
        term.write(Laststepx)
        term.write(" ")
        term.write(Laststepz)
        term.setCursorPos(1,3)
        term.write("Compass: ")
        term.write(Compass)
        sleep(5)
    end
end
function face(cardinal)
if cardinal == "north" or cardinal == 0 then
while Compass ~= 0 do
rotate("left")
end
end
if cardinal == "east" or cardinal == 1 then
while Compass ~= 1 do
rotate("left")
end
end
if cardinal == "south" or cardinal == 2 then
while Compass ~= 2 do
rotate("left")
end
end
if cardinal == "west" or cardinal == 3 then
while Compass ~= 3 do
rotate("left")
end    
end
end

function rotate(direc)
local ass = 0
if direc == "left" then
turtle.turnLeft()
ass = -1
end
if direc == "right" then
turtle.turnRight()
ass = 1
end
Compass = Compass + ass
if Compass == -1 then
Compass = 3
end
if Compass == 4 then
Compass = 0
end
end

function move(quan, bool)
if bool ~= true then
bool = false
end

local function poschange(change)
if Compass == 0 then
Xpos = Xpos + change
end
if Compass == 1 then
Zpos = Zpos + change
end
if Compass == 2 then
Xpos = Xpos - change
end
if Compass == 3 then
Zpos = Zpos - change
end
end


local count = 0
local ass = 0
if quan > 0 then
for i=1, quan do
if bool then
turtle.dig()
end
turtle.forward()
poschange(1)
end
end
if quan < 0 then
for i=1, -quan do
turtle.back()
poschange(-1)
end
end
end

function moveto(x,z)
face(0)
move(x-Xpos)
face(1)
move(z-Zpos)
end

function tempcompcalc()
if tempcomp == 0 then
Laststepx = Laststepx + 1
Laststep = Laststepx
elseif tempcomp == 2 then
Laststepx = Laststepx - 1
Laststep = Laststepx
elseif tempcomp == 3 then
Laststepz = Laststepz - 1
Laststep = Laststepz
elseif tempcomp == 1 then
Laststepz = Laststepz + 1
Laststep = Laststepz
end
    
end

function relquarry(leng, wid)
--- 0 = north 1 = east 2 = south 3= west
local track = 0
leng = leng + 1
while true do
while wid >= track do
move(leng, true)
track = track + 1
if wid <= track then
break
end
rotate("right")
move(1, true)
rotate("right")
move(leng, true)
track = track + 1
if wid <= track then
break
end
rotate("left")
move(1, true)
rotate("left")
end
track = 0

if Laststep == 0 then
moveto(Laststepx,Laststepz)
move(1,true)
rotate("right")
move(1, true)
tempcomp = Compass
rotate("right")
move(1, true)
tempcompcalc()


elseif(Laststep <= (leng-1)) then
moveto(Laststepx,Laststepz)
face(Laststepcard)
move(1,true)
rotate("right")
move(2, true)
move(-2)
tempcomp = Compass
rotate("right")
move(1, true)
tempcompcalc()


else
moveto(Laststepx,Laststepz)
face(Laststepcard)
move(1,true)
rotate("right")
Laststepcard = Compass
move(1, true)
turtle.digDown()
rotate("right")
tempcomp = Compass
move(2, true)
move(-1)
rotate("right")
move(1, true)
tempcompcalc()
Laststep = 0
end


moveto(0,0)
face(0)
turtle.digDown()
turtle.down()


end
end

function farmwater(leng, wid)
leng = leng -1
wid = wid -1
    while true do
track = leng - 1
    turtle.digDown()
    move(9)
while track > 0 do
    turtle.digDown()
    move(9,true)
    track = track - 1
end
    track = leng - 1

if wid == 0 then
    turtle.digDown()
    break
end
rotate("right")
turtle.digDown()
move(9, true)
rotate("right")

wid = wid -1
track = leng - 1
    turtle.digDown()
    move(9)
while track > 0 do
    turtle.digDown()
    move(9,true)
    track = track - 1
end
    track = leng - 1

if wid == 0 then
    turtle.digDown()
    break
end
wid = wid - 1
rotate("left")
turtle.digDown()
move(9, true)
rotate("left")

end
end
