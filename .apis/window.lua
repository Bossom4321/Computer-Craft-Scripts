require("utils")
require("displaymanager")

function createObject(xpos,ypos,text,isbutton)
    text = text or ""
    isbutton = isbutton or false
    
end


function fillColor(perwindow,color)
    reset = perwindow.getBackgroundColor()
    perwindow.setBackgroundColor(colornum(color))
    perwindow.clear()
end


function danceFloor(peripherial,size,colors)
    local colors = colors or {"orange", "yellow", "lime","pink","cyan","purple","blue","green","red"}
    peripherial = peripherial or term
    if peripheral.getType(peripherial) == "monitor" then
        peripherial.setTextScale(0.5)
    end
    local x, y = peripherial.getSize()
    wintable = {}
    roundedx = math.floor(x/size)
    roundedy = math.floor(y/size)
    remainderx = math.floor((x%size)/size)
    remaindery = math.floor((y%size)/size)
    lastremainderx = math.floor((x%size)%size)
    lastremaindery = math.floor((y%size)%size)

    


    
    for z=0,size-1 do
        
        startx = 1+((roundedx+remainderx))
        starty = 1+((roundedy+remaindery))
        endx = (roundedx+remainderx)+1
        endy = (roundedy+remaindery)+1
        for i=0,size-1 do
            --god bless you if you have to fix this in the future, this shit sucks, sucks to be you if your reading this

            table.insert(wintable,window.create(peripherial,    startx*(i)    ,    starty*(z)    ,   endx        ,   endy))

        end
        

        table.insert(wintable,window.create(peripherial,    ((roundedx+lastremainderx)*(size))    ,    ((roundedy+lastremaindery)*(z))    ,   endx        ,   endy))
    end
    last = nil
    for z=1, #wintable do
        rand = math.random(1,#colors)
    if #colors > 1 then
        if rand == last then
            if rand < #colors then
            rand = rand+1
            else
            rand = rand - 1
            end
        end
    end

        last = rand
        wintable[z].setBackgroundColor(colornum(colors[rand]))
        local x, y = wintable[z].getSize()
        
        --wintable[z].setBackgroundColor(colornum(colors[(z - 1) % #colors + 1]))
        wintable[z].clear()

        
    end

end
