// Keyboard Controls for Robotics Car
(function() {
    'use strict';
    
    let controlsEnabled = true;
    
    function initKeyboardControls() {
        console.log('🎮 Keyboard controls loaded');
        
        document.addEventListener('keydown', function(e) {
            if (!controlsEnabled) return;
            
            // Prevent default arrow key scrolling
            if(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.key)) {
                e.preventDefault();
            }
            
            // Map keys to button clicks
            const directionMap = {
                'ArrowUp': 'forward',
                'ArrowDown': 'backward',
                'ArrowLeft': 'left',
                'ArrowRight': 'right',
                ' ': 'stop'
            };
            
            const direction = directionMap[e.key];
            if (direction) {
                const button = document.querySelector(`[data-direction="${direction}"]`);
                if (button) {
                    button.click();
                    console.log(`🎮 Key pressed: ${e.key} → ${direction}`);
                }
            }
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initKeyboardControls);
    } else {
        initKeyboardControls();
    }
    
    // Export control functions
    window.robotCarControls = {
        setEnabled: function(enabled) {
            controlsEnabled = enabled;
            console.log(`🎮 Controls ${enabled ? 'enabled' : 'disabled'}`);
        },
        isEnabled: function() {
            return controlsEnabled;
        }
    };
})();