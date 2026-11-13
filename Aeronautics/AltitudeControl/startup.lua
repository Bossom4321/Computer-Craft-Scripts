package.path = package.path .. ";.apis/?.lua"
require("rsapi")
require("utils")
require("displaymanager")

-- ==========================================
-- PERIPHERAL WRAPS
-- ==========================================
local bl = peripheral.wrap("redstone_relay_0")
local br = peripheral.wrap("redstone_relay_1")
local fl = peripheral.wrap("redstone_relay_3")
local fr = peripheral.wrap("redstone_relay_2")

local velsens = peripheral.wrap("velocity_sensor_0")
local gimbal = peripheral.wrap("gimbal_sensor_0")
altisens = peripheral.wrap("altitude_sensor_0")

-- ==========================================
-- SHIP CONFIGURATION: Exact Shipyard Coordinates
-- ==========================================
local pos_fr = vector.new(20481013, 126, 20556795)
local pos_fl = vector.new(20481013, 126, 20556823)
local pos_bl = vector.new(20481038, 126, 20556823)
local pos_br = vector.new(20481038, 126, 20556795)

-- Turn off propellers initially with max power configuration
rAll(15,fr)
rAll(15,fl)
rAll(15,br)
rAll(15,bl)

-- ==========================================
-- GLOBAL CONTROL & UI VARIABLES
-- ==========================================
local target_altitude = 100
local kp_alt = 0.5 
local max_ascent_rate = 8.0 
local max_descent_rate = -2.0
local gravity = 9
magicnumber1 = 25

local pastvel = 0
local past_pitch = 0
local past_roll = 0
local integral_error = 0
local ki_alt = 0.005 

-- UI Shared State variables
local input = ""
local saveFile = "altitude_save.txt"
local current_alt_display = 0
local roll_rate_display = 0
local pitch_rate_display = 0
local propscaled_display = 0

----------------------------------------
-- 1. PERSISTENCE FUNCTIONS (Save/Load)
----------------------------------------
local function saveAltitude(alt)
    local f = fs.open(saveFile, "w")
    if f then
        f.write(tostring(alt))
        f.close()
    end
end

local function loadAltitude()
    if fs.exists(saveFile) then
        local f = fs.open(saveFile, "r")
        if f then
            local data = f.readAll()
            f.close()
            local num = tonumber(data)
            if num then return num end
        end
    end
    return nil
end

-- Load previous target or keep default
local savedAlt = loadAltitude()
if savedAlt then
    target_altitude = savedAlt
else
    saveAltitude(target_altitude)
end

----------------------------------------
-- 2. UNIFIED DISPLAY MANAGER
----------------------------------------
local function drawUI()
    rclear()
    outnl("=== Quadcopter Flight System ===")
    outnl("Target Altitude : " .. target_altitude-5)
    outnl("Current Altitude: " .. (math.floor(current_alt_display * 10) / 10))
    outnl("Roll Rate       : " .. (math.floor(roll_rate_display * 100) / 100))
    outnl("Pitch Rate      : " .. (math.floor(pitch_rate_display * 100) / 100))
    outnl("Prop Redstone   : " .. (math.floor(propscaled_display * 10) / 10))
    outnl("--------------------------------")
    outnl("Enter new altitude: " .. input)
end

----------------------------------------
-- 3. USER INPUT LOOP (Thread 1)
----------------------------------------
local function inputLoop()
    while true do
        drawUI()
        local event, p1 = os.pullEvent()

        if event == "char" then
            -- Allow digits and a minus sign for manual coordinate entries
            if p1:match("[%d%-]") then 
                input = input .. p1
            end
        elseif event == "key" then
            if p1 == keys.backspace then
                input = input:sub(1, -2)
            elseif p1 == keys.enter then
                local new_alt = tonumber(input)
                if new_alt then
                    target_altitude = new_alt+5
                    saveAltitude(target_altitude)
                    integral_error = 0 -- Reset memory to avoid jumps when target shifts
                end
                input = ""
            end
        end
    end
end

----------------------------------------
-- 4. FLIGHT CORE LOOP (Thread 2)
----------------------------------------
local function controlLoop()
    while true do
        -- 1. Altitude Control (Position -> Velocity)
        local current_altitude = altisens.getHeight() 
        current_alt_display = current_altitude -- Pass to UI thread
        local altitude_error = target_altitude - current_altitude
        
        -- INTEGRAL WINDUP FIX: Only use the integral when close to the target
        if math.abs(altitude_error) < 5 then
            integral_error = integral_error + altitude_error
            integral_error = math.max(-50, math.min(50, integral_error))
        else
            integral_error = 0 
        end
        
        -- Add the integral boost to the desired climb rate
        local desired_roc = (altitude_error * kp_alt) + (integral_error * ki_alt)
        desired_roc = math.max(max_descent_rate, math.min(max_ascent_rate, desired_roc))

        -- 2. Velocity Control (Velocity -> Acceleration)
        local mass = sublevel.getMass()
        local currentvel = velsens.getVelocity()

        local acceleration = (desired_roc - currentvel) * 2.5
        pastvel = currentvel

        -- Add gravity to the acceleration so the ship knows it must fight it to hover
        local total_accel = acceleration + gravity

        -- F = m * a
        local force = mass * total_accel
        -- Map required force to a 0-15 redstone scale
        local forceclamped = scaleRange(force, 0, mass*magicnumber1, 0, 15)

        local switch = scaleRange(rIn("left"), 0, 15, 0, 1)
        local propforce = forceclamped * switch
        local propscaled = math.max(propforce, rIn("right"))
        propscaled_display = propscaled -- Pass to UI thread

        -- ==========================================
        -- CENTER OF MASS LOAD DISTRIBUTION
        -- ==========================================
        local com = sublevel.getCenterOfMass()
        
        local function getWeight(pos)
            if not com then return 1 end
            local dist = math.sqrt((pos.x - com.x)^2 + (pos.z - com.z)^2)
            return 1 / (dist + 0.0001) 
        end

        local w_fr = getWeight(pos_fr)
        local w_fl = getWeight(pos_fl)
        local w_bl = getWeight(pos_bl)
        local w_br = getWeight(pos_br)

        local total_w = w_fr + w_fl + w_bl + w_br

        -- Normalize weights
        local weight_fr = (w_fr / total_w) * 4
        local weight_fl = (w_fl / total_w) * 4
        local weight_bl = (w_bl / total_w) * 4
        local weight_br = (w_br / total_w) * 4

        local base_fr = propscaled * weight_fr
        local base_fl = propscaled * weight_fl
        local base_br = propscaled * weight_br
        local base_bl = propscaled * weight_bl

        -- ==========================================
        -- PITCH & ROLL PID CORRECTIONS
        -- ==========================================
        local angles = gimbal.getAngles()
        local roll = angles[1]  
        local pitch = angles[2] 

        local dt = 0.1
        local roll_rate = (roll - past_roll) / dt
        local pitch_rate = (pitch - past_pitch) / dt

        past_roll = roll
        past_pitch = pitch
        
        roll_rate_display = roll_rate   -- Pass to UI thread
        pitch_rate_display = pitch_rate -- Pass to UI thread

        local kp_pr = 0.15 
        local kd_pr = 0.08
        local pitch_correction = (pitch * kp_pr) + (pitch_rate * kd_pr)
        local roll_correction = (roll * kp_pr) + (roll_rate * kd_pr)

        local raw_fr = base_fr + pitch_correction + roll_correction
        local raw_fl = base_fl + pitch_correction - roll_correction
        local raw_br = base_br - pitch_correction + roll_correction
        local raw_bl = base_bl - pitch_correction - roll_correction

        local max_thrust = math.max(raw_fr, raw_fl, raw_br, raw_bl)
        local min_thrust = math.min(raw_fr, raw_fl, raw_br, raw_bl)

        local hover_thrust = 15 * (gravity / 20) 

        -- Basic Redstone bounds shifting
        local shift = 0
        if max_thrust > 15 then
            shift = 15 - max_thrust 
        elseif min_thrust < 0 then
            shift = 0 - min_thrust 
        end

        -- PRIORITY STABILIZATION: The "Freefall Power Cut" Fix
        local max_after_bounds = max_thrust + shift
        local tilt_demand = math.max(math.abs(pitch_correction), math.abs(roll_correction))
        
        local stabilization_baseline = math.min(hover_thrust, propscaled)
        
        if max_after_bounds < stabilization_baseline then
            local boost_factor = math.min(1.0, tilt_demand / 4.0)
            local required_boost = stabilization_baseline - max_after_bounds
            shift = shift + (required_boost * boost_factor)
        end

        -- Apply shift and final clamp
        local thrust_fr = math.max(0, math.min(15, raw_fr + shift))
        local thrust_fl = math.max(0, math.min(15, raw_fl + shift))
        local thrust_br = math.max(0, math.min(15, raw_br + shift))
        local thrust_bl = math.max(0, math.min(15, raw_bl + shift))

        local final_fr = thrust_fr
        local final_fl = thrust_fl
        local final_br = thrust_br
        local final_bl = thrust_bl

        -- Apply cleanly rounded integers to Redstone Relays
        rAll(math.floor(15 - final_fr + 0.5), fr)
        rAll(math.floor(15 - final_fl + 0.5), fl)
        rAll(math.floor(15 - final_br + 0.5), br)
        rAll(math.floor(15 - final_bl + 0.5), bl)
        
        -- Update the terminal display with the fresh physics calculations
        drawUI()
        
        sleep(0.1)
    end
end

----------------------------------------
-- 5. RUN BOTH THREADS SIMULTANEOUSLY
----------------------------------------
parallel.waitForAny(inputLoop, controlLoop)