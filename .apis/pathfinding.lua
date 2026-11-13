require("tableapi")

    cardinals = {"north","east","south","west"}
    increment = {-1,1,1,-1}
    --north = -1 on z
    --south = +1 on z
    --west =  -1 on x
    --east = +1 on x

function facingoffset(direction)
    return increment[findindex(cardinals,direction)]
end


function move(val,facing,mex,mez,dayperipherial)
    function sensorcheck()
        while true do
        if (dayperipherial.getSkyLightLevel()) ~= 15 or turtle.detectUp() then
            term.write("1")
            coveredpanic()
        else
            return false
        end
    end
    end
    
    function coveredpanic()
        while (dayperipherial.getSkyLightLevel()) ~= 15 or turtle.detectUp() do
            turtle.back()
            turtle.up()
            turtle.up()
            while turtle.detect() do
            turtle.up()
            end 
            turtle.forward()
        end
    end

    if val >= 1 then
        for x=1, val do
        
            while turtle.detect() do
            turtle.up()
            end
            turtle.forward()
            while not(turtle.detectDown()) do
                turtle.down()
            end
            sensorcheck()
        end
    elseif val <= 1 then
        for x=1, (val*-1) do
            turtle.back()
        end
    end

    cardval = increment[findindex(cardinals,facing)]

    if facing == "north" or facing == "south" then
        mez = mez+(val*(cardval))
    else
        mex = mex+(val*(cardval))
    end

    return mex, mez
end

function turnwhere(goalx, goalz, mex, mez, facing)
    --fuck this code
    --if you ever need to fix it may god have mercy on your soul
    if goalx == mex then
        goal = goalz
        me = mez
    else
        goal = goalx
        me = mex
    end
    
    if goal-me > 1 then
        val = 1
    else
        val = -1
    end

    index = findindex(cardinals,facing)

    if index == 1 then
        clamped = 4
    else
        clamped = index -1
    end

    if val == increment[clamped] then
        return "left"
    else
        return "right"
    end

end

function turn(direction,facing)
    index = findindex(cardinals,facing)
    if string.lower(direction) == "left" then
        turtle.turnLeft()
        
        if index == 1 then
            return "west"
        else
            return cardinals[index-1]
        end
    elseif string.lower(direction) == "right" then
        turtle.turnRight()
        if index == 4 then
            return "north"
        else
            return cardinals[index+1]
        end
    end
end

function cube_1step_daysearch(facing,mex,mez,x,z,dayperipherial,turnmemory,startx,startz)
    

    facing = string.lower(facing)
    faceval = facingoffset(facing)

    --turing subroutine
    if turnmemory and (mex == x or mez == z or (mex == startx and not(facing == "north" or facing == "south")) or (mez == startz and not(facing == "east" or facing =="west"))) then
        turnvar = turnwhere(x,z,mex,mez,facing)

        facing = turn(turnvar,facing)
        mex, mez = move(1,facing,mex,mez,dayperipherial)
        facing = turn(turnvar,facing)
        turnmemory = false
    else
    turnmemory = true
    mex, mez = move(1,facing,mex,mez,dayperipherial)
    end
    return mex, mez, facing, turnmemory
end