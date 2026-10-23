from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.src.db.seed import DEFAULT_PROBLEM_ID, seed_initial_data
from services.api.src.db.session import AsyncSessionLocal
from services.api.src.main import app
from tests.e2e.test_vertical_slice import run_pipeline_step


@pytest.mark.asyncio
async def test_cpp_pipeline_accepted():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    cpp_source = r"""
#include <iostream>
#include <vector>
#include <unordered_map>
#include <sstream>

using namespace std;

int main() {
    string line;
    if (!getline(cin, line)) return 0;
    stringstream ss(line);
    vector<int> nums;
    int x;
    while (ss >> x) nums.push_back(x);
    int target;
    if (!(cin >> target)) return 0;

    unordered_map<int, int> seen;
    for (int i = 0; i < (int)nums.size(); ++i) {
        int comp = target - nums[i];
        if (seen.find(comp) != seen.end()) {
            cout << seen[comp] << " " << i << "\n";
            return 0;
        }
        seen[nums[i]] = i;
    }
    return 0;
}
"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "cpp",
                "source_code": cpp_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        # Run pipeline step
        await run_pipeline_step(sub_id, attempt_id)

        # Verify final verdict
        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "ACCEPTED"
        assert detail["language"] == "cpp"
        assert len(detail["test_results"]) == 3


@pytest.mark.asyncio
async def test_cpp_pipeline_compile_error():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    bad_cpp = "int main() { syntax_error; return 0; }"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "cpp",
                "source_code": bad_cpp,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "COMPILE_ERROR"
        assert len(detail["test_results"]) == 0


@pytest.mark.asyncio
async def test_java_pipeline_accepted():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    java_source = r"""
import java.util.*;

public class Solution {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        if (!scanner.hasNextLine()) return;
        String line = scanner.nextLine().trim();
        if (line.isEmpty() && scanner.hasNextLine()) {
            line = scanner.nextLine().trim();
        }
        String[] parts = line.split("\\s+");
        int[] nums = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            nums[i] = Integer.parseInt(parts[i]);
        }
        if (!scanner.hasNextInt()) return;
        int target = scanner.nextInt();

        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int comp = target - nums[i];
            if (seen.containsKey(comp)) {
                System.out.println(seen.get(comp) + " " + i);
                return;
            }
            seen.put(nums[i], i);
        }
    }
}
"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "java",
                "source_code": java_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "ACCEPTED"
        assert detail["language"] == "java"
        assert len(detail["test_results"]) == 3


@pytest.mark.asyncio
async def test_java_pipeline_compile_error():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    bad_java = "public class Solution { invalid_code }"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "java",
                "source_code": bad_java,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "COMPILE_ERROR"
        assert len(detail["test_results"]) == 0


@pytest.mark.asyncio
async def test_rust_pipeline_accepted():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    rust_source = r"""
use std::collections::HashMap;
use std::io::{self, BufRead};

fn main() {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    let line1 = match lines.next() {
        Some(Ok(l)) => l,
        _ => return,
    };
    let line2 = match lines.next() {
        Some(Ok(l)) => l,
        _ => return,
    };

    let nums: Vec<i32> = line1
        .split_whitespace()
        .filter_map(|s| s.parse().ok())
        .collect();
    let target: i32 = match line2.trim().parse() {
        Ok(t) => t,
        _ => return,
    };

    let mut seen = HashMap::new();
    for (i, &num) in nums.iter().enumerate() {
        let comp = target - num;
        if let Some(&prev_idx) = seen.get(&comp) {
            println!("{} {}", prev_idx, i);
            return;
        }
        seen.insert(num, i);
    }
}
"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "rust",
                "source_code": rust_source,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "ACCEPTED"
        assert detail["language"] == "rust"
        assert len(detail["test_results"]) == 3


@pytest.mark.asyncio
async def test_rust_pipeline_compile_error():
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    bad_rust = "fn main() { invalid_rust_syntax; }"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/submissions",
            json={
                "problem_id": str(DEFAULT_PROBLEM_ID),
                "language": "rust",
                "source_code": bad_rust,
                "client_request_id": str(uuid4()),
            },
        )
        assert resp.status_code == 201
        sub_id = resp.json()["submission_id"]
        attempt_id = resp.json()["attempt_id"]

        await run_pipeline_step(sub_id, attempt_id)

        resp_detail = await client.get(f"/api/v1/submissions/{sub_id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["status"] == "COMPLETED"
        assert detail["verdict"] == "COMPILE_ERROR"
        assert len(detail["test_results"]) == 0
