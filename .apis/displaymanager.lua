--require("displaymanager")       NO .lua!!!
--rclear()    sets cursor back to 1,1
--outnl
--out
--sizeX
--sizeY
--scroll/smoothScroll
require("utils")





function rclear(peripherial)
    peripherial = peripherial or term
    peripherial.setTextColor(1)
    peripherial.setBackgroundColor(32768)
    peripherial.clear()
    peripherial.setCursorPos(1,1)
end

function outnl(text,peripherial,colortxt,colorbg,linex,liney)
    peripherial = peripherial or term
    text = text or ""
    text = tostring(text)
    colortxt = colortxt or peripherial.getTextColor()
    colortxt = colornum(colortxt)
    colorbg = colorbg or peripherial.getBackgroundColor()
    colorbg = colornum(colorbg)
    local x, y = peripherial.getCursorPos()
    linex = linex or x
    liney = liney or y
    
    

    
    peripherial.setTextColor(colortxt)
    peripherial.setBackgroundColor(colorbg)
    peripherial.setCursorPos(linex,liney)
    peripherial.write(text)
    peripherial.setCursorPos(1,liney+1)
end

function out(text,peripherial, colortxt,colorbg,linex,liney)
    peripherial = peripherial or term
    text = text or ""
    text = tostring(text)
    colortxt = colortxt or peripherial.getTextColor()
    colortxt = colornum(colortxt)
    colorbg = colorbg or peripherial.getBackgroundColor()
    colorbg = colornum(colorbg)
    local x, y = peripherial.getCursorPos()
    linex = linex or x
    liney = liney or y



    local x, y = peripherial.getCursorPos()
    peripherial.setTextColor(colortxt)
    peripherial.setBackgroundColor(colorbg)
    peripherial.write(text)
end


function outCenternl(text,peripherial, colortxt,colorbg,liney)
    peripherial = peripherial or term
    text = text or ""
    text = tostring(text)
    colortxt = colortxt or peripherial.getTextColor()
    colortxt = colornum(colortxt)
    colorbg = colorbg or peripherial.getBackgroundColor()
    colorbg = colornum(colorbg)
    local x, y = peripherial.getCursorPos()
    liney = liney or y
    peripherial.setCursorPos((sizeX(peripherial)/2)-(#text/2),liney)
    peripherial.setTextColor(colortxt)
    peripherial.setBackgroundColor(colorbg)
    peripherial.write(text)
    peripherial.setCursorPos(1,liney+1)

end

function outCenter(text,peripherial, colortxt,colorbg,liney)
    peripherial = peripherial or term
    text = text or ""
    text = tostring(text)
    colortxt = colortxt or peripherial.getTextColor()
    colortxt = colornum(colortxt)
    colorbg = colorbg or peripherial.getBackgroundColor()
    colorbg = colornum(colorbg)
    local x, y = peripherial.getCursorPos()
    liney = liney or y
    peripherial.setCursorPos((sizeX(peripherial)/2)-(#text/2),liney)
    peripherial.setTextColor(colortxt)
    peripherial.setBackgroundColor(colorbg)
    peripherial.write(text)
end


function sizeX(peripherial)
    peripherial = peripherial or term
    local x, y = peripherial.getSize()
    return x
end

function sizeY(peripherial)
    peripherial = peripherial or term
    local x, y = peripherial.getSize()
    return y
end

--function horizontalScroll(text,direction)
--direction = string.lower(direction) or "right"




--end



function scroll(value,peripherial)
    peripherial = peripherial or term
    peripherial.scroll(value)
end

function smoothScroll(value,speed,peripherial)
    peripherial = peripherial or term
    speed = speed or 1
    if value > 0 then
    for i=1,value do
    peripherial.scroll(1)
    sleep(speed)
    end
else
    for i=-1,value,-1 do
    peripherial.scroll(-1)
    sleep(speed)
    end
end
end

