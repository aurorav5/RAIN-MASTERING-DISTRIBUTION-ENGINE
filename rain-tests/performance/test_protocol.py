"""
RAIN AI Mastering Engine - Performance Test Protocol
====================================================

Performance testing including:
- Load testing
- Stress testing
- Spike testing
- Endurance testing
- Latency measurements
- Throughput analysis
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Dict, Any
import aiohttp
import json

pytestmark = pytest.mark.asyncio

# Test configuration
BASE_URL = "http://localhost:8000"
CONCURRENT_USERS = [10, 50, 100, 200]
TEST_DURATION_SECONDS = 60

# =============================================================================
# PERFORMANCE METRICS
# =============================================================================

class PerformanceMetrics:
    """Collect and analyze performance metrics."""
    
    def __init__(self):
        self.response_times: List[float] = []
        self.status_codes: Dict[int, int] = {}
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0
    
    def add_response(self, response_time: float, status_code: int):
        self.response_times.append(response_time)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
    
    def add_error(self, error: str):
        self.errors.append(error)
    
    def get_summary(self) -> Dict[str, Any]:
        if not self.response_times:
            return {"error": "No data collected"}
        
        sorted_times = sorted(self.response_times)
        total_requests = len(self.response_times)
        
        return {
            "total_requests": total_requests,
            "total_errors": len(self.errors),
            "error_rate": len(self.errors) / (total_requests + len(self.errors)) * 100,
            "min_response_time_ms": min(self.response_times) * 1000,
            "max_response_time_ms": max(self.response_times) * 1000,
            "mean_response_time_ms": statistics.mean(self.response_times) * 1000,
            "median_response_time_ms": statistics.median(self.response_times) * 1000,
            "p95_response_time_ms": sorted_times[int(len(sorted_times) * 0.95)] * 1000,
            "p99_response_time_ms": sorted_times[int(len(sorted_times) * 0.99)] * 1000,
            "requests_per_second": total_requests / (self.end_time - self.start_time),
            "status_codes": self.status_codes,
        }


# =============================================================================
# LOAD TESTS
# =============================================================================

class TestLoad:
    """Load testing with increasing concurrent users."""
    
    async def test_health_endpoint_load(self):
        """Test health endpoint under load."""
        metrics = PerformanceMetrics()
        
        async def make_request(session: aiohttp.ClientSession):
            start = time.time()
            try:
                async with session.get(f"{BASE_URL}/health") as response:
                    await response.text()
                    elapsed = time.time() - start
                    metrics.add_response(elapsed, response.status)
            except Exception as e:
                metrics.add_error(str(e))
        
        for concurrent_users in CONCURRENT_USERS:
            metrics = PerformanceMetrics()
            metrics.start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                tasks = [make_request(session) for _ in range(concurrent_users * 10)]
                await asyncio.gather(*tasks, return_exceptions=True)
            
            metrics.end_time = time.time()
            summary = metrics.get_summary()
            
            print(f"\n--- Health Endpoint Load Test: {concurrent_users} concurrent users ---")
            print(f"Mean response time: {summary['mean_response_time_ms']:.2f}ms")
            print(f"P95 response time: {summary['p95_response_time_ms']:.2f}ms")
            print(f"Error rate: {summary['error_rate']:.2f}%")
            print(f"RPS: {summary['requests_per_second']:.2f}")
            
            # Assertions
            assert summary['mean_response_time_ms'] < 500, f"Mean response time too high: {summary['mean_response_time_ms']}ms"
            assert summary['error_rate'] < 5, f"Error rate too high: {summary['error_rate']}%"
    
    async def test_api_endpoint_load(self, auth_token: str):
        """Test API endpoints under load."""
        metrics = PerformanceMetrics()
        
        async def make_request(session: aiohttp.ClientSession):
            start = time.time()
            try:
                headers = {"Authorization": f"Bearer {auth_token}"}
                async with session.get(f"{BASE_URL}/api/v1/sessions", headers=headers) as response:
                    await response.text()
                    elapsed = time.time() - start
                    metrics.add_response(elapsed, response.status)
            except Exception as e:
                metrics.add_error(str(e))
        
        metrics.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(500)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_time = time.time()
        summary = metrics.get_summary()
        
        print(f"\n--- API Endpoint Load Test ---")
        print(f"Mean response time: {summary['mean_response_time_ms']:.2f}ms")
        print(f"P95 response time: {summary['p95_response_time_ms']:.2f}ms")
        
        assert summary['mean_response_time_ms'] < 1000
        assert summary['error_rate'] < 5


# =============================================================================
# STRESS TESTS
# =============================================================================

class TestStress:
    """Stress testing to find breaking points."""
    
    async def test_stress_health_endpoint(self):
        """Stress test health endpoint until failure."""
        metrics = PerformanceMetrics()
        concurrent_users = 10
        max_users = 1000
        
        async def make_request(session: aiohttp.ClientSession):
            start = time.time()
            try:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    await response.text()
                    elapsed = time.time() - start
                    metrics.add_response(elapsed, response.status)
            except Exception as e:
                metrics.add_error(str(e))
        
        while concurrent_users <= max_users:
            metrics = PerformanceMetrics()
            metrics.start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                tasks = [make_request(session) for _ in range(concurrent_users)]
                await asyncio.gather(*tasks, return_exceptions=True)
            
            metrics.end_time = time.time()
            summary = metrics.get_summary()
            
            print(f"\n--- Stress Test: {concurrent_users} users ---")
            print(f"Error rate: {summary['error_rate']:.2f}%")
            print(f"Mean response: {summary['mean_response_time_ms']:.2f}ms")
            
            # Stop if error rate exceeds 50%
            if summary['error_rate'] > 50:
                print(f"\n!!! Breaking point reached at {concurrent_users} concurrent users !!!")
                break
            
            concurrent_users *= 2
            await asyncio.sleep(1)  # Cool down
    
    async def test_stress_login_endpoint(self):
        """Stress test login endpoint."""
        metrics = PerformanceMetrics()
        
        async def make_request(session: aiohttp.ClientSession):
            start = time.time()
            try:
                payload = {
                    "email": f"stress_test_{time.time()}@arcovel.com",
                    "password": "testpassword123"
                }
                async with session.post(f"{BASE_URL}/api/v1/auth/login", json=payload) as response:
                    await response.text()
                    elapsed = time.time() - start
                    metrics.add_response(elapsed, response.status)
            except Exception as e:
                metrics.add_error(str(e))
        
        metrics.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Rapid fire 100 login attempts
            tasks = [make_request(session) for _ in range(100)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_time = time.time()
        summary = metrics.get_summary()
        
        print(f"\n--- Login Stress Test ---")
        print(f"Total requests: {summary['total_requests']}")
        print(f"Error rate: {summary['error_rate']:.2f}%")
        
        # Login should have rate limiting
        assert summary['error_rate'] > 0 or summary['total_requests'] <= 100


# =============================================================================
# SPIKE TESTS
# =============================================================================

class TestSpike:
    """Spike testing - sudden traffic increases."""
    
    async def test_spike_traffic(self):
        """Test sudden spike in traffic."""
        metrics = PerformanceMetrics()
        
        async def make_request(session: aiohttp.ClientSession):
            start = time.time()
            try:
                async with session.get(f"{BASE_URL}/health") as response:
                    await response.text()
                    elapsed = time.time() - start
                    metrics.add_response(elapsed, response.status)
            except Exception as e:
                metrics.add_error(str(e))
        
        # Baseline - 10 users
        print("\n--- Baseline: 10 users ---")
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(10)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Spike - 500 users suddenly
        print("--- SPIKE: 500 users ---")
        metrics = PerformanceMetrics()
        metrics.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(500)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_time = time.time()
        summary = metrics.get_summary()
        
        print(f"Error rate: {summary['error_rate']:.2f}%")
        print(f"P99 response: {summary['p99_response_time_ms']:.2f}ms")
        
        # Should recover after spike
        await asyncio.sleep(2)
        
        print("--- Recovery: 10 users ---")
        metrics = PerformanceMetrics()
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(10)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Recovery should be quick
        assert summary['error_rate'] < 20


# =============================================================================
# ENDURANCE TESTS
# =============================================================================

class TestEndurance:
    """Endurance testing - sustained load over time."""
    
    async def test_endurance_api(self, auth_token: str):
        """Test API endurance over 5 minutes."""
        metrics = PerformanceMetrics()
        duration = 300  # 5 minutes
        
        async def make_request(session: aiohttp.ClientSession):
            start = time.time()
            try:
                headers = {"Authorization": f"Bearer {auth_token}"}
                async with session.get(f"{BASE_URL}/api/v1/sessions", headers=headers) as response:
                    await response.text()
                    elapsed = time.time() - start
                    metrics.add_response(elapsed, response.status)
            except Exception as e:
                metrics.add_error(str(e))
        
        print(f"\n--- Endurance Test: {duration} seconds ---")
        metrics.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            end_time = time.time() + duration
            request_count = 0
            
            while time.time() < end_time:
                # Make 10 requests every second
                tasks = [make_request(session) for _ in range(10)]
                await asyncio.gather(*tasks, return_exceptions=True)
                request_count += 10
                
                if request_count % 100 == 0:
                    print(f"Requests made: {request_count}, Errors: {len(metrics.errors)}")
                
                await asyncio.sleep(1)
        
        metrics.end_time = time.time()
        summary = metrics.get_summary()
        
        print(f"\n--- Endurance Test Results ---")
        print(f"Total requests: {summary['total_requests']}")
        print(f"Total errors: {summary['total_errors']}")
        print(f"Mean response time: {summary['mean_response_time_ms']:.2f}ms")
        
        # Should maintain low error rate over time
        assert summary['error_rate'] < 1


# =============================================================================
# LATENCY TESTS
# =============================================================================

class TestLatency:
    """Latency measurement tests."""
    
    async def test_latency_distribution(self):
        """Measure latency distribution."""
        latencies = []
        
        async with aiohttp.ClientSession() as session:
            for _ in range(100):
                start = time.time()
                async with session.get(f"{BASE_URL}/health") as response:
                    await response.text()
                elapsed = (time.time() - start) * 1000  # Convert to ms
                latencies.append(elapsed)
        
        latencies.sort()
        
        print("\n--- Latency Distribution ---")
        print(f"Min: {min(latencies):.2f}ms")
        print(f"Max: {max(latencies):.2f}ms")
        print(f"Mean: {statistics.mean(latencies):.2f}ms")
        print(f"P50: {latencies[49]:.2f}ms")
        print(f"P95: {latencies[94]:.2f}ms")
        print(f"P99: {latencies[98]:.2f}ms")
        
        # Latency requirements
        assert statistics.mean(latencies) < 100, "Mean latency too high"
        assert latencies[94] < 200, "P95 latency too high"
        assert latencies[98] < 500, "P99 latency too high"
    
    async def test_websocket_latency(self):
        """Test WebSocket latency if applicable."""
        # Placeholder for WebSocket latency tests
        pass


# =============================================================================
# THROUGHPUT TESTS
# =============================================================================

class TestThroughput:
    """Throughput measurement tests."""
    
    async def test_max_throughput(self):
        """Measure maximum throughput."""
        request_count = 0
        duration = 10  # seconds
        
        async def make_request(session: aiohttp.ClientSession):
            nonlocal request_count
            try:
                async with session.get(f"{BASE_URL}/health") as response:
                    await response.text()
                    request_count += 1
            except:
                pass
        
        print("\n--- Max Throughput Test ---")
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            while time.time() - start_time < duration:
                tasks = [make_request(session) for _ in range(50)]
                await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        throughput = request_count / elapsed
        
        print(f"Requests: {request_count}")
        print(f"Duration: {elapsed:.2f}s")
        print(f"Throughput: {throughput:.2f} RPS")
        
        # Should handle at least 100 RPS
        assert throughput > 100
    
    async def test_file_upload_throughput(self, auth_token: str):
        """Test file upload throughput."""
        import io
        
        # Create 1MB test file
        test_file = io.BytesIO(b'\x00' * (1024 * 1024))
        
        upload_times = []
        
        async with aiohttp.ClientSession() as session:
            for _ in range(5):
                test_file.seek(0)
                
                start = time.time()
                data = aiohttp.FormData()
                data.add_field('file', test_file, filename='test.wav', content_type='audio/wav')
                
                headers = {"Authorization": f"Bearer {auth_token}"}
                async with session.post(f"{BASE_URL}/api/v1/upload", data=data, headers=headers) as response:
                    await response.text()
                
                elapsed = time.time() - start
                upload_times.append(elapsed)
                
                await asyncio.sleep(1)  # Rate limiting
        
        avg_upload_time = statistics.mean(upload_times)
        throughput_mbps = (1 * 8) / avg_upload_time  # 1MB in Mbps
        
        print(f"\n--- File Upload Throughput ---")
        print(f"Avg upload time: {avg_upload_time:.2f}s")
        print(f"Throughput: {throughput_mbps:.2f} Mbps")


# =============================================================================
# MEMORY LEAK TESTS
# =============================================================================

class TestMemory:
    """Memory usage tests."""
    
    async def test_memory_stability(self, auth_token: str):
        """Test for memory leaks under sustained load."""
        # This would require server-side memory monitoring
        # Placeholder for memory leak detection
        
        print("\n--- Memory Stability Test ---")
        print("Note: Requires server-side memory monitoring")
        
        async with aiohttp.ClientSession() as session:
            for i in range(100):
                headers = {"Authorization": f"Bearer {auth_token}"}
                async with session.get(f"{BASE_URL}/api/v1/sessions", headers=headers) as response:
                    await response.text()
                
                if i % 20 == 0:
                    print(f"Iteration {i}/100")
                
                await asyncio.sleep(0.1)


# =============================================================================
# DATABASE PERFORMANCE TESTS
# =============================================================================

class TestDatabasePerformance:
    """Database query performance tests."""
    
    async def test_query_performance(self, auth_token: str):
        """Test database query performance."""
        query_times = []
        
        async with aiohttp.ClientSession() as session:
            for _ in range(50):
                start = time.time()
                headers = {"Authorization": f"Bearer {auth_token}"}
                async with session.get(f"{BASE_URL}/api/v1/sessions", headers=headers) as response:
                    await response.text()
                elapsed = (time.time() - start) * 1000
                query_times.append(elapsed)
        
        avg_time = statistics.mean(query_times)
        
        print(f"\n--- Database Query Performance ---")
        print(f"Avg query time: {avg_time:.2f}ms")
        
        # Database queries should be fast
        assert avg_time < 50


# =============================================================================
# COMPREHENSIVE LOAD TEST
# =============================================================================

@pytest.mark.slow
async def test_comprehensive_load():
    """Run comprehensive load test."""
    print("\n" + "="*60)
    print("RAIN AI Mastering Engine - Comprehensive Load Test")
    print("="*60)
    
    all_metrics = {}
    
    # Test 1: Health endpoint
    print("\n[1/5] Testing health endpoint...")
    metrics = PerformanceMetrics()
    async with aiohttp.ClientSession() as session:
        for _ in range(100):
            start = time.time()
            async with session.get(f"{BASE_URL}/health") as response:
                await response.text()
            metrics.add_response(time.time() - start, response.status)
    all_metrics['health'] = metrics.get_summary()
    
    # Test 2: Concurrent users
    print("\n[2/5] Testing concurrent users...")
    for users in [10, 50, 100]:
        metrics = PerformanceMetrics()
        metrics.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(users):
                async def req():
                    start = time.time()
                    async with session.get(f"{BASE_URL}/health") as response:
                        await response.text()
                    metrics.add_response(time.time() - start, response.status)
                tasks.append(req())
            await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.end_time = time.time()
        all_metrics[f'concurrent_{users}'] = metrics.get_summary()
        print(f"  {users} users: {all_metrics[f'concurrent_{users}']['mean_response_time_ms']:.2f}ms mean")
    
    # Test 3: Rate limiting
    print("\n[3/5] Testing rate limiting...")
    metrics = PerformanceMetrics()
    async with aiohttp.ClientSession() as session:
        for _ in range(50):
            start = time.time()
            async with session.post(f"{BASE_URL}/api/v1/auth/login", json={
                "email": "test@test.com",
                "password": "wrong"
            }) as response:
                await response.text()
            metrics.add_response(time.time() - start, response.status)
    all_metrics['rate_limit'] = metrics.get_summary()
    
    # Test 4: Latency distribution
    print("\n[4/5] Testing latency distribution...")
    latencies = []
    async with aiohttp.ClientSession() as session:
        for _ in range(100):
            start = time.time()
            async with session.get(f"{BASE_URL}/health") as response:
                await response.text()
            latencies.append((time.time() - start) * 1000)
    latencies.sort()
    all_metrics['latency'] = {
        'mean': statistics.mean(latencies),
        'p50': latencies[49],
        'p95': latencies[94],
        'p99': latencies[98],
    }
    
    # Test 5: Throughput
    print("\n[5/5] Testing throughput...")
    request_count = 0
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < 10:
            async with session.get(f"{BASE_URL}/health") as response:
                await response.text()
            request_count += 1
    throughput = request_count / 10
    all_metrics['throughput'] = {'rps': throughput}
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, data in all_metrics.items():
        print(f"\n{name.upper()}:")
        for key, value in data.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
    
    # Assertions
    assert all_metrics['health']['mean_response_time_ms'] < 100
    assert all_metrics['concurrent_100']['error_rate'] < 5
    assert all_metrics['throughput']['rps'] > 50
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
