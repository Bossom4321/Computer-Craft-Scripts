function actionDict(action)
        if action == "condition_fluid_inventory" then
            action = "condition_liquid_inventory"
        end
        if action == "empty_tank" then
            action = "void_liquid"
        end
        if action == "empty_tank" then
            action = "void_liquid"
        end
        return action 
end

function sideDict(side)
    if side == "top" then
    return "up"
    end
    if side == "down" then
        return "bottom"
    end
    return string.lower(side)
    
end

function setSides(per,sides)
    function isinsideDict(table, what)
    for i = 1, #table do
        if sideDict(table[i]) == what then
        return true
        end
    end
    return false
    end
    local bottom = isinsideDict(sides,"bottom")
    local top = isinsideDict(sides,"up")
    local north = isinsideDict(sides,"north")
    local south = isinsideDict(sides,"south")
    local west = isinsideDict(sides,"west")
    local east = isinsideDict(sides,"east")
    per.setSides(bottom,top,north,south,west,east)
   
    

end

function setSide(per,side)
    side = sideDict(side)
    per.setSide(side)
end

function coordMathNumberAdd(area1,x,y,z)
    return({area1[1]+x,area1[2]+y,area1[3]+z})
end
function coordMathNumberSub(area1,x,y,z)
    return({area1[1]-x,area1[2]-y,area1[3]-z})
end
function coordMathNumberMult(area1,x,y,z)
    return({area1[1]*x,area1[2]*y,area1[3]*z})
end
function coordMathNumberDiv(area1,x,y,z)
    return({area1[1]/x,area1[2]/y,area1[3]/z})
end


function coordMathCoordAdd(area1,area2)
    return({area1[1]+area2[1],area1[2]+area2[2],area1[3]+area2[3]})
end
function coordMathCoordSub(area1,area2)
    return({area1[1]-area2[1],area1[2]-area2[2],area1[3]-area2[3]})
end
function coordMathCoordMult(area1,area2)
    return({area1[1]*area2[1],area1[2]*area2[2],area1[3]*area2[3]})
end
function coordMathCoordDiv(area1,area2)
    return({area1[1]/area2[1],area1[2]/area2[2],area1[3]/area2[3]})
end

function dronePosVec(per)
local temp = per.getDronePositionVec()
return {temp.x,temp.y,temp.z}
end

function setOrder(per, order)
    local order = string.lower(order)
    if order == "closest" then
        per.setBlockOrder("closest")
    end
    if order == "high" then
        per.setBlockOrder("highToLow")
    end
    if order == "low" then
        per.setBlockOrder("lowToHigh")
    end
end

function getPos(per)
    return per.getDronePosition()
end

function clearArea(per)
    per.clearArea()
end

function isDone(per)
    return per.isActionDone()
end

function evaluate(per,operation,operator,number,area1,area2,isand)
    area2 = area2 or area1
    isand = isand or false
    per.setOperator(operator)
    per.setCount(number)
    setSides(per,{"top","bottom","north","south","east","west"})
    per.setIsAndFunction(isand)
    setArea(per, area1, area2)
    setAction(per,operation)
    while not per.isActionDone() do
        sleep(0.1)
    end
    return per.evaluateCondition()
end


--not working correctly, but im sick and tired this, god speed future me who needs this
--function countBlocksCondGTET(per,area1,area2,list,number)
function countBlocksCondGTET(per,area1,area2,number)
    per.clearBlacklistItemFilter()
    per.clearWhitelistItemFilter()
    -- for x=1, #list do
    -- --per.addWhitelistItemFilter(list[x][1],list[x][2],list[x][3])
    -- --per.addWhitelistItemFilter(list[x][1],false,false)
    -- end
    return evaluate(per,"condition_block",">=",number,area1,area2)
end


function setArea(per,vector1,vector2,type)
    vector2 = vector2 or vector1
    type = type or "filled"
    clearArea(per)
    per.addArea(vector1[1],vector1[2],vector1[3],vector2[1],vector2[2],vector2[3],type)
end

function addArea(per,vector1,vector2,type)
    vector2 = vector2 or vector1
    type = type or "filled"
    per.addArea(vector1[1],vector1[2],vector1[3],vector2[1],vector2[2],vector2[3],type)
end

function removeArea(per, vector1,vector2,type)
    vector2 = vector2 or vector1
    type = type or "filled"
    per.removeArea(vector1[1],vector1[2],vector1[3],vector2[1],vector2[2],vector2[3],type)
end

function setAction(per, action)
    action = actionDict(action)
    per.setAction(action)
end

function dig(per,diggingtool,order,sides)
    diggingtool = diggingtool or false
    order = order or "high"
    sides = sides or {"top","bottom","north","south","east","west"}
    if type(sides) == type("") then
        sides = {sides}
    end
    setSides(per,sides)
    per.setRequiresTool(diggingtool)
    setOrder(per,order)
    setAction(per,"dig")
end

function goTo(per,area,finishedonarrival)
    finishedonarrival = finishedonarrival or false
    setArea(per,area)
    per.setAction("goto")
    while finishedonarrival do
        sleep(0.1)
        finishedonarrival = not per.isActionDone()
    end
end

