# Frontend Integration Guide: Dashboard Collaboration System (React)

## Overview

This guide provides human-readable instructions for React developers to implement dashboard collaboration features. You'll learn how to integrate real-time editing sessions and widget locking into your React application.

## 📋 What You'll Build

When users edit dashboards collaboratively, you'll implement:

1. **Dashboard Editing Sessions** - Show who's currently editing
2. **Widget Locking** - Prevent conflicts when editing widgets
3. **Real-time Presence** - Live updates of who's active
4. **Conflict Prevention** - Stop users from editing locked widgets

## 🚀 Quick Start Flow

Here's the typical user journey your code will handle:

```
User opens dashboard → Start editing session → Show active users
     ↓
User clicks widget → Check lock status → Acquire lock → Edit widget
     ↓
User saves widget → Release lock → Update dashboard
     ↓
User leaves dashboard → Stop editing session
```

## 📚 Core Concepts

### 1. Dashboard Editing Session
- Created when user opens dashboard in edit mode
- Shows "User A is editing this dashboard"
- Automatically tracks last activity
- Other users see who's currently editing

### 2. Widget Locking
- Prevents multiple users editing same widget simultaneously
- Locks expire after 60 seconds (configurable)
- Heartbeat keeps locks active while editing
- Clear visual indicators show locked widgets

## 🛠️ Implementation Guide

### Step 1: Create Collaboration Service

Create a service class to handle all collaboration API calls:

```javascript
// services/collaborationService.js
class CollaborationService {
  constructor(baseURL) {
    this.baseURL = baseURL;
    this.activeSession = null;
    this.activeLocks = new Map();
    this.intervals = new Map();
  }

  // Start editing session when dashboard opens
  async startDashboardEditing(dashboardId, userInfo) {
    const response = await fetch(`${this.baseURL}/dashboards/${dashboardId}/edit/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userInfo)
    });
    
    const session = await response.json();
    this.activeSession = session;
    return session;
  }

  // Stop editing session when dashboard closes
  async stopDashboardEditing(dashboardId) {
    await fetch(`${this.baseURL}/dashboards/${dashboardId}/edit/stop`, {
      method: 'POST'
    });
    this.activeSession = null;
  }

  // Acquire lock when user clicks widget
  async acquireWidgetLock(dashboardId, widgetId) {
    const response = await fetch(`${this.baseURL}/dashboards/${dashboardId}/widgets/lock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ widget_id: widgetId })
    });
    
    const lock = await response.json();
    this.activeLocks.set(widgetId, lock);
    return lock;
  }

  // Release lock when done editing
  async releaseWidgetLock(dashboardId, widgetId) {
    await fetch(`${this.baseURL}/dashboards/${dashboardId}/widgets/lock`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ widget_id: widgetId })
    });
    
    this.activeLocks.delete(widgetId);
  }

  // Check if widget is available for editing
  async getWidgetStatus(dashboardId, widgetId) {
    const response = await fetch(
      `${this.baseURL}/dashboards/${dashboardId}/widgets/${widgetId}/status`
    );
    return await response.json();
  }

  // Get all active users and locks
  async getActiveSessions(dashboardId) {
    const response = await fetch(
      `${this.baseURL}/dashboards/${dashboardId}/active-sessions`
    );
    return await response.json();
  }
}
```

### Step 2: Create Main Dashboard Edit Component

This is your main React component that handles the entire collaboration flow:

```javascript
// components/DashboardEditor.jsx
import React, { useState, useEffect } from 'react';
import CollaborationService from '../services/collaborationService';

const DashboardEditor = ({ dashboardId, user }) => {
  const [collaboration] = useState(() => new CollaborationService(API_URL));
  const [activeUsers, setActiveUsers] = useState([]);
  const [widgetLocks, setWidgetLocks] = useState({});
  const [myLocks, setMyLocks] = useState(new Set());

  // 🎯 STEP 1: Start editing session when component mounts
  useEffect(() => {
    const initializeEditing = async () => {
      try {
        // Start the editing session
        await collaboration.startDashboardEditing(dashboardId, {
          user_id: user.id,
          user_name: user.name,
          user_email: user.email
        });
        
        console.log('Editing session started');
        
        // Start polling for active users
        startActiveUsersPolling();
        
      } catch (error) {
        console.error('Failed to start editing:', error);
      }
    };

    initializeEditing();

    // 🧹 Cleanup: Stop session when component unmounts
    return () => {
      collaboration.stopDashboardEditing(dashboardId);
      console.log('Editing session stopped');
    };
  }, [dashboardId, user, collaboration]);

  // 🔄 STEP 2: Poll for active users and locks
  const startActiveUsersPolling = () => {
    const interval = setInterval(async () => {
      try {
        const data = await collaboration.getActiveSessions(dashboardId);
        setActiveUsers(data.active_sessions);
        
        // Convert locks to easy-to-use object
        const locksMap = {};
        data.widget_locks.forEach(lock => {
          locksMap[lock.widget_id] = lock;
        });
        setWidgetLocks(locksMap);
      } catch (error) {
        console.warn('Failed to fetch active sessions:', error);
      }
    }, 10000); // Poll every 10 seconds

    return () => clearInterval(interval);
  };

  // 🖱️ STEP 3: Handle widget click (lock acquisition)
  const handleWidgetClick = async (widgetId) => {
    try {
      // First, check if widget is available
      const status = await collaboration.getWidgetStatus(dashboardId, widgetId);
      
      if (status.is_locked && status.locked_by_user_id !== user.id) {
        // Widget is locked by someone else - show message
        alert(`⚠️ This widget is being edited by ${status.locked_by}`);
        return;
      }
      
      if (!status.is_locked || status.locked_by_user_id === user.id) {
        // Widget is available - acquire lock
        const lock = await collaboration.acquireWidgetLock(dashboardId, widgetId);
        
        if (lock.success) {
          // Add to my locks and enable editing
          setMyLocks(prev => new Set([...prev, widgetId]));
          enableWidgetEditing(widgetId);
        }
      }
    } catch (error) {
      console.error('Failed to handle widget click:', error);
    }
  };

  // 💾 STEP 4: Handle widget save (lock release)
  const handleWidgetSave = async (widgetId) => {
    try {
      await collaboration.releaseWidgetLock(dashboardId, widgetId);
      setMyLocks(prev => {
        const newSet = new Set(prev);
        newSet.delete(widgetId);
        return newSet;
      });
      disableWidgetEditing(widgetId);
    } catch (error) {
      console.error('Failed to release widget lock:', error);
    }
  };

  const enableWidgetEditing = (widgetId) => {
    // Your widget editing enable logic here
    console.log(`Editing enabled for widget ${widgetId}`);
  };

  const disableWidgetEditing = (widgetId) => {
    // Your widget editing disable logic here
    console.log(`Editing disabled for widget ${widgetId}`);
  };

  return (
    <div className="dashboard-editor">
      {/* 👥 Collaboration Presence Sidebar */}
      <CollaborationSidebar 
        activeUsers={activeUsers}
        widgetLocks={widgetLocks}
        currentUser={user}
      />
      
      {/* 📊 Dashboard Content */}
      <DashboardContent 
        widgets={dashboardWidgets}
        onWidgetClick={handleWidgetClick}
        onWidgetSave={handleWidgetSave}
        lockedWidgets={widgetLocks}
        myLocks={myLocks}
      />
    </div>
  );
};

export default DashboardEditor;
```

### Step 3: Create Collaboration Sidebar Component

Show who's currently editing and which widgets are locked:

```javascript
// components/CollaborationSidebar.jsx
import React from 'react';

const CollaborationSidebar = ({ activeUsers, widgetLocks, currentUser }) => {
  const otherUsers = activeUsers.filter(user => user.user_id !== currentUser.id);
  
  return (
    <div className="collaboration-sidebar">
      <h3>👥 Currently Editing</h3>
      
      {/* Show current user */}
      <div className="user-item current-user">
        <span className="user-dot you"></span>
        <span>You ({currentUser.name})</span>
      </div>
      
      {/* Show other users */}
      {otherUsers.map(user => (
        <div key={user.session_id} className="user-item">
          <span className="user-dot"></span>
          <span>{user.user_name}</span>
          <small>Editing for {formatDuration(user.connected_at)}</small>
        </div>
      ))}
      
      {/* Show active locks */}
      {Object.keys(widgetLocks).length > 0 && (
        <div className="locks-section">
          <h4>🔒 Active Locks</h4>
          {Object.values(widgetLocks).map(lock => (
            <div key={lock.widget_id} className="lock-item">
              <span>Widget {lock.widget_id.slice(0, 8)}...</span>
              <span>By: {lock.user_name}</span>
              <small>Expires in {lock.time_remaining}s</small>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Helper function to format duration
const formatDuration = (startTime) => {
  const minutes = Math.floor((Date.now() - new Date(startTime)) / 60000);
  return `${minutes}m`;
};

export default CollaborationSidebar;
```

### Step 4: Enhance Widget Components

Update your widget components to show lock status:

```javascript
// components/Widget.jsx
import React from 'react';

const Widget = ({ 
  widget, 
  onEditClick, 
  onSave, 
  isLocked, 
  lockedBy, 
  isMyLock 
}) => {
  const canEdit = !isLocked || isMyLock;
  
  return (
    <div className={`widget ${isLocked ? 'widget-locked' : ''}`}>
      <div className="widget-header">
        <h4>{widget.name}</h4>
        
        {/* Lock Status Indicator */}
        {isLocked && (
          <div className="lock-indicator">
            {isMyLock ? (
              <span className="lock-badge my-lock">🔒 You're editing</span>
            ) : (
              <span className="lock-badge others-lock">
                🔒 Locked by {lockedBy}
              </span>
            )}
          </div>
        )}
      </div>
      
      <div className="widget-content">
        {/* Your widget content here */}
      </div>
      
      <div className="widget-actions">
        {canEdit ? (
          <button 
            onClick={() => onEditClick(widget.id)}
            className="edit-button"
          >
            {isMyLock ? 'Save Changes' : 'Edit Widget'}
          </button>
        ) : (
          <button disabled className="edit-button disabled">
            🔒 Currently locked
          </button>
        )}
      </div>
    </div>
  );
};

export default Widget;
```

## 🔄 Real-World Usage Flow

### Scenario: Two Users Editing Same Dashboard

**User A's Experience:**
1. Opens dashboard → Editing session starts → Heartbeat begins (every 45s)
2. Clicks Widget 1 → Acquires lock → Sees "You're editing"
3. Starts editing Widget 1 → Widget heartbeat begins (every 10s)

**User B's Experience:**
1. Opens dashboard → Sees "User A is editing" → Heartbeat begins (every 45s)
2. Clicks Widget 1 → Sees "Locked by User A" → Can't edit
3. Clicks Widget 2 → Acquires lock → Starts editing Widget 2 → Widget heartbeat begins (every 10s)

### 🚨 IMPORTANT: Heartbeat Schedule

**Dashboard Heartbeat**: Every 45 seconds
- Prevents APScheduler from cleaning up your session
- Required even if you're just viewing (not editing widgets)

**Widget Heartbeat**: Every 10 seconds  
- Keeps widget locks active while editing
- Stops automatically when lock is released

### Timeline Flow:

```
Time 0:  User A opens dashboard → Session A created
Time 5:  User B opens dashboard → Session B created → User A sees User B
Time 10: User A clicks Widget 1 → Lock A1 acquired
Time 12: User B clicks Widget 1 → Sees "Locked by User A" → Can't edit
Time 15: User B clicks Widget 2 → Lock B2 acquired
Time 20: User A saves Widget 1 → Lock A1 released
Time 25: User B can now edit Widget 1 if desired
```

## 🛡️ Error Handling & Edge Cases

### Network Failures
```javascript
const handleWidgetClickWithRetry = async (widgetId, retries = 3) => {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await collaboration.acquireWidgetLock(dashboardId, widgetId);
    } catch (error) {
      if (attempt === retries) {
        alert('Network error - please try again');
        throw error;
      }
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
};
```

### Session Timeouts
```javascript
// 🚨 CRITICAL: Dashboard heartbeat prevents APScheduler cleanup
// APScheduler cleans sessions older than 5 minutes (300 seconds)
// Send heartbeat every 45 seconds to stay active
useEffect(() => {
  const heartbeatInterval = setInterval(async () => {
    try {
      await collaboration.refreshDashboardEditing(dashboardId, user);
    } catch (error) {
      console.warn('Dashboard heartbeat failed - session may be cleaned up:', error);
    }
  }, 45000); // Every 45 seconds (safety margin)
  
  return () => clearInterval(heartbeatInterval);
}, [dashboardId, user, collaboration]);
```

## 🎨 Styling Recommendations

```css
/* Collaboration indicators */
.user-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  display: inline-block;
  margin-right: 8px;
}

.user-dot.you {
  background: #3b82f6;
}

.widget-locked {
  opacity: 0.6;
  pointer-events: none;
}

.lock-badge {
  background: #fef3c7;
  border: 1px solid #f59e0b;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.lock-badge.my-lock {
  background: #d1fae5;
  border-color: #10b981;
}
```

## ✅ Testing Your Implementation

### Manual Testing Checklist

- [ ] User can start editing session
- [ ] Active users appear in sidebar
- [ ] Widget locking prevents conflicts
- [ ] Lock releases properly on save
- [ ] Session stops on dashboard close
- [ ] Error messages show for locked widgets

### Example Test Data
```javascript
// Mock data for testing
const mockUsers = [
  { user_id: 'user-1', user_name: 'Alice', connected_at: new Date() },
  { user_id: 'user-2', user_name: 'Bob', connected_at: new Date(Date.now() - 300000) }
];

const mockLocks = {
  'widget-1': { widget_id: 'widget-1', user_name: 'Alice', time_remaining: 45 }
};
```

## 🚀 Production Readiness

### Performance Considerations
- Debounce frequent API calls
- Use WebSocket for real-time updates (if available)
- Implement client-side caching
- Lazy load collaboration data

### Security Considerations
- Validate user permissions before editing
- Implement proper authentication
- Sanitize user input
- Rate limit API calls

## 📞 Support & Troubleshooting

### Common Issues

**Issue:** "Widget is locked" message appears incorrectly
**Solution:** Check that lock release is called on widget save

**Issue:** Active users list doesn't update
**Solution:** Verify polling interval is running and API responses are valid

**Issue:** Session doesn't start
**Solution:** Check authentication tokens and API endpoint URLs

**Issue:** "No active editing session found" when stopping
**Solution:** 🚨 APScheduler cleaned up the session due to missing heartbeats
- Ensure dashboard heartbeat runs every 45 seconds
- Check network connectivity for heartbeat failures
- The system now handles this gracefully by considering cleanup successful

**Issue:** Sessions disappear unexpectedly
**Solution:** APScheduler removes sessions with last_activity older than 5 minutes
- Implement dashboard heartbeat as shown above
- Monitor heartbeat failures in browser console

### Debugging Tips
```javascript
// Add debug logging
console.log('🔧 Collaboration Debug:', {
  activeSession: collaboration.activeSession,
  activeLocks: Array.from(collaboration.activeLocks.keys()),
  currentUser: user.id
});
```

## 🎯 Summary

You now have a complete implementation guide for React dashboard collaboration. The system provides:

- ✅ Real-time user presence
- ✅ Conflict-free widget editing
- ✅ Clear visual indicators
- ✅ Robust error handling
- ✅ Easy integration with existing components

Start with the basic implementation and enhance with real-time features as needed. Your users will appreciate the smooth collaborative editing experience!