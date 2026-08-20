#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for monitor platform
"""

import asyncio
import json
import websockets
import requests
import time

async def test_websocket():
    """Test WebSocket connection"""
    print("Testing WebSocket connection...")
    
    uri = "ws://localhost:8765/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            
            # Send test message
            test_msg = {
                "msgId": "test-001",
                "ts": int(time.time() * 1000),
                "deviceId": "TEST-001",
                "type": "heartbeat",
                "payload": {}
            }
            
            await websocket.send(json.dumps(test_msg))
            print(f"✓ Sent test message: {test_msg['type']}")
            
            # Receive response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            resp_data = json.loads(response)
            print(f"✓ Received response: {resp_data.get('type')}")
            
            return True
            
    except Exception as e:
        print(f"✗ WebSocket test failed: {e}")
        return False

def test_http_api():
    """Test HTTP API"""
    print("\nTesting HTTP API...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Test root endpoint
        resp = requests.get(f"{base_url}/", timeout=5)
        if resp.status_code == 200:
            print("✓ HTTP root endpoint OK")
        else:
            print(f"✗ HTTP root returned {resp.status_code}")
            return False
        
        # Test API status
        resp = requests.get(f"{base_url}/api/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ API status: {data}")
        else:
            print(f"✗ API status returned {resp.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ HTTP test failed: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("Monitor Platform Test")
    print("=" * 60)
    
    # Test HTTP API
    http_ok = test_http_api()
    
    # Test WebSocket
    ws_ok = asyncio.run(test_websocket())
    
    print("\n" + "=" * 60)
    if http_ok and ws_ok:
        print("All tests passed!")
    else:
        print("Some tests failed. Make sure the monitor platform is running.")
        print("Start with: python3 monitor_platform/server.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
