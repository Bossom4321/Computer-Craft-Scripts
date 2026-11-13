function getMass()
    return sublevel.getMass()
end

function getVelocity()
    sublevel.getVelocity()
end
    
function getCoords()
    return sublevel.getLastPose().position
end

function getCOM()
return sublevel.getLogicalPose().position
end