-- File: utils
-- This file contains my custom, reusable functions.
require("tableapi")

local colors = { "white", "orange", "magenta", "lightblue", "yellow", "lime", "pink", "gray", "lightgray", "cyan",
  "purple", "blue", "brown", "green", "red", "black" }
local colorsid = { "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f" }



--get color hash-number from color name as input
function colornum(color)
  if (type(color) ~= type(1)) then
    color = string.gsub(string.gsub(string.lower(color), "_", ""), " ", "")
    local index = findindex(colors, color)
    if not (index) then
      index = 1
    end
    return 2 ^ (index - 1)
  end

  return color
end

--get color hash-number from minecrafts colorsid, with a string-number or letterinput
--(rare use case, most likely use other one)
function colorid(color)
  if (type(color) ~= type(1)) then
    local index = findindex(colorsid, color)
    if not (index) then
      index = 1
    end
    return 2 ^ (index - 1)
  end

  return color
end

function replace(str, whattbl, withtbl)
  str = str or ""
  whattbl = whattbl or { "" }
  withtbl = withtbl or { "" }
  if type(whattbl) == "string" then
    whattbl = { whattbl }
  end
  if type(withtbl) == "string" then
    withtbl = { withtbl }
  end
  for i = 1, #whattbl do
    str = string.gsub(str, whattbl[i], withtbl[i])
  end
  return str
end

--inclusive check if within a range of numbers
function inRange(input, startvar, endvar)
  if input >= startvar and input <= endvar then
    return true
  end
  return false
end

function isNumber(inputvar)
  if tonumber(isNumber) then
    return true
  end
  return false
end

function split(inputstr, sep)
    t = {}
    -- Pattern: matches everything that is not the separator
    for str in string.gmatch(inputstr, "([^" .. sep .. "]+)") do
        table.insert(t, str)
    end
    return t
end






function slope(x1, y1, x2, y2)
  return ((y2 - y1) / (x2 - x1))
end

function ywithx(slope, x, x1, y1)
  return (slope*(x - x1) + y1)
end

function xwithy(slope, y, x1, y1)
  return (((y - y1) + (slope * x1)) / slope)
end

function tracecircumfrence(h,k,radius,t)
  pi = math.pi
  local function solveu(u)
    return (-pi/2)+u*pi
  end
  local function xpos(u)
    return radius*math.cos(u)
  end

  yscale = 6/9

  local function ypos(u)
    return radius*math.sin(u) * yscale
  end


  


  local t = solveu(t)

  local x = h + xpos(t)
  local y= k + ypos(t)
  local adjx = 2*h-x
  local adjy= 2*k-y
  return x,y,adjx,adjy
  
end

function scaleRange(x,startog,endog,startnew,endnew)
  temp = startnew + ((x-startog)*(endnew-startnew))/(endog-startog)
  temp = math.max(temp,startnew)
  temp = math.min(temp,endnew)
  return temp
end