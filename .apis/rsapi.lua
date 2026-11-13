--Logic gates no not, since thats built in
function rAnd(side1,side2,peripherial)
    peripherial = peripherial or redstone
    return (peripherial.getInput(side1) and peripherial.getInput(side2))
end

function rOr(side1,side2,peripherial)
    peripherial = peripherial or redstone
    return (peripherial.getInput(side1) or peripherial.getInput(side2))
end

function rNand(side1,side2,peripherial)
    peripherial = peripherial or redstone
    return not(peripherial.getInput(side1) and peripherial.getInput(side2))
end

function rNor(side1,side2,peripherial)
    peripherial = peripherial or redstone
    return not(peripherial.getInput(side1) or peripherial.getInput(side2))
end

function rXor(side1,side2,peripherial)
    peripherial = peripherial or redstone
    return (peripherial.getInput(side1) ~= peripherial.getInput(side2))
end

function rXnor(side1,side2,peripherial)
    peripherial = peripherial or redstone
    return not(peripherial.getInput(side1) ~= peripherial.getInput(side2))
end


function rPulse(side,length,power,peripherial)
    length = length or 0.1
    power = power or 15
    peripherial = peripherial or redstone
    peripherial.setAnalogueOutput(side, 15)
    sleep(length)
    peripherial.setAnalogueOutput(side, 0)
end

function rToggle(side,power,peripherial)
    power = power or 15
    peripherial = peripherial or redstone
    if(peripherial.getInput(side)) then
        peripherial.setAnalogueOutput(0)
else
    peripherial.setAnalogueOutput(side,power)
end   
end

function rOut(side,power,peripherial)
    power = power or 15
    peripherial = peripherial or redstone
    peripherial.setAnalogueOutput(side, power)
end

function rIn(side,peripherial)
    peripherial = peripherial or redstone
return peripherial.getAnalogInput(side)
end

function rReset(peripherial)
    peripherial = peripherial or redstone
    peripherial.setAnalogueOutput("top", 0)
    peripherial.setAnalogueOutput("bottom", 0)
    peripherial.setAnalogueOutput("right", 0)
    peripherial.setAnalogueOutput("left", 0)
    peripherial.setAnalogueOutput("front", 0)
    peripherial.setAnalogueOutput("back", 0)
end

function rAll(power,peripherial)
    peripherial = peripherial or redstone
    peripherial.setAnalogueOutput("top", power)
    peripherial.setAnalogueOutput("bottom", power)
    peripherial.setAnalogueOutput("right", power)
    peripherial.setAnalogueOutput("left", power)
    peripherial.setAnalogueOutput("front", power)
    peripherial.setAnalogueOutput("back", power)
end