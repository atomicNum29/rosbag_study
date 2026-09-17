# ROS2 MCAP Camera / IMU Viewer

ROS2 rosbag 디렉터리의 카메라 영상과 gyro/accel을 공통 시간축으로 재생하는 PySide6 데스크톱 프로그램입니다. **기존 루트 uv 프로젝트**의 의존성과 가상환경을 사용합니다.

## 설치와 실행

ROS Jazzy 및 `rosbag2_storage_mcap`, `rosbag2_py`, `rclpy`, `rosidl_runtime_py`, `sensor_msgs`, `cv_bridge`가 설치되거나 빌드되어 있어야 합니다. ROS 모듈은 pip/uv로 설치하지 않습니다.

```bash
cd /home/cu/projects/python-workspace
source /opt/ros/jazzy/setup.bash
# 직접 빌드한 ROS라면 위 명령 대신:
# source <ROS2_BUILD_PATH>/install/setup.bash
uv sync
uv run python -m rosbag_viewer
# 또는 시작과 동시에 bag 열기
uv run python -m rosbag_viewer /home/cu/rosbag_2026-09-12_2
# 파일 경로로 실행하는 방법
uv run python rosbag_viewer/main.py /path/to/bag_directory
```

현재 프로젝트는 Python 3.12를 사용합니다. ROS 확장 모듈의 Python minor 버전과 실행 인터프리터가 일치해야 합니다. Jazzy의 기존 `cv_bridge` 바이너리는 NumPy 1.x ABI로 빌드되어 있어 NumPy 2에서 오류가 발생하므로, 루트 `pyproject.toml`과 `uv.lock`에 `numpy>=1.26.4,<2`, `opencv-python>=4.11,<4.12`를 반영했습니다. 기존 pandas, pyarrow, matplotlib 의존성은 유지했습니다.

동일한 의존성 추가 명령:

```bash
uv add 'numpy>=1.26.4,<2' 'opencv-python>=4.11,<4.12' pyside6 pyqtgraph
```

## 토픽과 시간 설정

기본 토픽은 다음과 같습니다.

| 용도 | 토픽 | 메시지 타입 |
| --- | --- | --- |
| 영상 | `/camera/fisheye1/image_raw` | `sensor_msgs/msg/Image` |
| Gyro | `/camera/gyro/sample` | `sensor_msgs/msg/Imu` |
| Accel | `/camera/accel/sample` | `sensor_msgs/msg/Imu` |

`config.py`의 `ViewerConfig` / `default_series()`에서 변경하거나 실행 인자로 지정합니다. Gyro와 accel에 같은 IMU 토픽을 지정해도 됩니다.

```bash
uv run python -m rosbag_viewer /path/to/bag \
  --image-topic /camera/image_raw \
  --gyro-topic /imu/data --accel-topic /imu/data \
  --timestamp header --cache-mib 64 --temp-dir /tmp
```

- `header` 모드는 유효한 `header.stamp`를 사용합니다. 없거나 0이면 해당 메시지의 record timestamp로 대체하며 상태 표시줄에 대체 횟수를 표시합니다.
- 공통 0초는 **선택된 영상 및 시계열 메시지의 최소 유효 timestamp**입니다. header 모드에서는 metadata의 record 시작 시각과 다를 수 있습니다. 표시 범위도 선택한 데이터의 끝까지입니다.
- epoch를 float로 변환한 뒤 빼지 않고, 정수 nanoseconds에서 시작 시각을 뺀 다음 상대 seconds로 변환합니다.
- 이미지 및 시계열의 `record_ns`에 원래 record timestamp를 보존합니다. 원점은 `BagDataSource.origin_ns`입니다.
- 서로 다른 센서 clock domain을 자동 보정하지 않습니다. header가 record 시간과 호환되지 않거나 센서마다 시간 기준이 다르면 `--timestamp record`로 전체 데이터를 동일한 record 기준에서 열 수 있습니다.
- timestamp가 역순으로 기록된 데이터는 안정 정렬합니다. 중복 시각의 영상은 기록 순서상 마지막 프레임을 선택합니다.

## 사용법

상단 **Open bag…**으로 `metadata.yaml`이 있는 디렉터리를 선택합니다. 분할 MCAP은 rosbag2 reader가 metadata에 따라 읽습니다. 로딩은 작업 스레드에서 진행하며 메시지 수와 디스크 캐시 크기를 표시합니다. **Cancel loading**으로 중단할 수 있습니다. 토픽 누락/타입 오류 시 실제 토픽 목록을 안내합니다. 정상 로드 후 상단 경로에 마우스를 올리면 전체 토픽 목록을 확인할 수 있습니다.

| 조작 | 동작 |
| --- | --- |
| Play / Pause, Space | 재생 / 일시정지 |
| Previous / Next, Left / Right | 현재 시각보다 엄격히 이전 / 이후인 영상 timestamp로 이동 |
| Shift+Left / Shift+Right | -1초 / +1초 |
| 슬라이더 | 전체 시간 범위 탐색, 일반 길이의 bag에서 ms 정밀도 |
| 그래프 노란 세로선 드래그 | 영상, 두 cursor, 슬라이더, 시간 표시 동시 이동 |
| 그래프 빈 영역 좌클릭 | 해당 시각으로 이동 |
| 속도 선택 | 0.25x / 0.5x / 1x / 2x |

그래프의 X축은 연결되어 확대·이동을 공유합니다. 세로 splitter로 영상/그래프 높이를 조절할 수 있습니다. 영상은 종횡비를 유지합니다. 재생 끝에서는 정지하고, 다시 Play하면 처음부터 시작합니다. 첫 영상보다 이른 시각에는 영상을 표시하지 않습니다. 중간 프레임 누락 구간에서는 해당 시각 이하의 가장 최근 영상을 유지합니다.

## 데이터 접근 및 성능

첫 로드 때 선택된 토픽을 한 번 순회합니다. IMU 등 수치 데이터는 NumPy 배열로 보관합니다. 영상은 header를 확인하기 위해 ROS 메시지로 역직렬화하지만, **모든 프레임을 영상 배열로 디코딩하여 RAM에 저장하지 않습니다.** 직렬화 바이트를 임시 파일에 기록하고 timestamp, record timestamp, offset, length만 메모리에 보관합니다.

seek에서는 `np.searchsorted(..., side="right") - 1`로 프레임을 찾고, 파일 offset으로 직접 읽어 `cv_bridge`로 RGB 변환합니다. 읽은 프레임은 기본 최대 64 MiB LRU 캐시에 보관합니다. 단일 프레임이 예산보다 크면 표시만 하고 캐시에 넣지 않습니다. mono8, mono16, RGB/BGR 등 cv_bridge가 RGB8로 변환할 수 있는 Image encoding을 지원합니다. mono16은 고정 16→8bit 스케일로 표시합니다.

이 버전은 **MCAP 자체의 chunk index를 seek에 사용하지 않는 디스크 인덱스 방식**입니다. 압축된 MCAP보다 큰 임시 공간이 필요할 수 있으며, 원시 직렬화 이미지 전체 크기만큼 디스크를 사용합니다. `--temp-dir`로 충분한 공간이 있는 디스크를 선택하세요. 파일은 닫기, 재열기, 로딩 실패/취소 시 정리합니다. 디스크 공간 부족은 로딩 오류로 표시됩니다. 최초 스캔은 전체 길이에 비례하며 재실행 시 다시 수행합니다.

Qt timer는 약 60 Hz로 UI를 갱신하고, 재생 위치는 monotonic clock의 경과 시간 × 재생속도로 계산합니다. 느린 갱신에서 프레임을 건너뛰어 시간 흐름을 유지합니다. 단일 프레임 읽기/디코딩은 GUI 스레드에서 실행하므로 매우 큰 프레임이나 느린 디스크에서는 잠깐 지연될 수 있습니다. cursor/slider의 프로그램 갱신은 `QSignalBlocker`로 감싸 피드백 루프를 방지합니다.

## 파일 역할과 확장

| 파일 | 역할 |
| --- | --- |
| `config.py` | 기본 토픽, timestamp 모드, 캐시 예산, `SeriesSpec` |
| `data.py` | `BagDataSource`, `TimeSeriesData` (`ImuData` 별칭), `ImageSource`, 디스크 인덱스와 LRU |
| `playback.py` | monotonic clock 재생, 공통 seek, 프레임 이동, 시간 포맷 |
| `window.py` | 비동기 bag 로딩, 영상, 범용 시계열 그래프, 컨트롤, 이벤트 동기화 |
| `main.py`, `__main__.py` | CLI 및 앱 진입점 |
| `tests/test_viewer.py` | ROS 없이 수행하는 코어 및 offscreen GUI 회귀 테스트 |
| `tests/test_ros_integration.py` | 실제 ROS 직렬화/MCAP 생성·로드·디코딩 통합 테스트 |

RPM, 모터 전류, cmd_vel 등은 `ViewerConfig.series`에 `SeriesSpec`을 추가하면 로더와 GUI가 해당 필드와 그래프를 자동으로 추가합니다. 예를 들어 `geometry_msgs/msg/Twist`의 선속도/각속도는 아래처럼 별도 그래프로 등록합니다.

```python
from rosbag_viewer.config import SeriesSpec, ViewerConfig, default_series

config = ViewerConfig(series=default_series() + (
    SeriesSpec("Command linear velocity", "/cmd_vel", "geometry_msgs/msg/Twist",
               ("linear.x", "linear.y", "linear.z"), ("x", "y", "z"), "m/s"),
    SeriesSpec("Command angular velocity", "/cmd_vel", "geometry_msgs/msg/Twist",
               ("angular.x", "angular.y", "angular.z"), ("x", "y", "z"), "rad/s"),
))
# MainWindow(config)로 실행. header가 없는 Twist는 record timestamp를 사용합니다.
```

현재 필드 접근은 점으로 구분된 숫자 속성을 지원합니다. 가변 길이 배열/복합 변환이 필요한 타입은 `field_value` 또는 별도 extractor 확장이 필요합니다.

## 검증

```bash
source /opt/ros/jazzy/setup.bash
uv run python -m unittest discover -s rosbag_viewer/tests -v
```

GUI 테스트는 offscreen 모드로 실행합니다. ROS가 없으면 MCAP 통합 테스트는 skip됩니다. 테스트는 중복/역순 timestamp, 공통 IMU 토픽, record 시간 보존, 이미지 직접 읽기와 캐시 제한, 실제 시간 기반 재생과 속도 변경, 끝 도달, frame step 및 slider/cursor 이벤트 동기화를 확인합니다.

API 참고: [rosbag2 SequentialReader 테스트](https://github.com/ros2/rosbag2/blob/rolling/rosbag2_py/test/test_sequential_reader.py), [Qt QSignalBlocker](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSignalBlocker.html).

이 작업 환경에서 ROS Jazzy를 source한 상태로 6개 테스트를 통과했습니다. 기존 `/home/cu/rosbag_2026-09-12_2` (3.5GB)를 offscreen GUI로 열어 영상 2,689개, gyro 17,923개, accel 5,553개, 상대시간 약 89.681초를 확인했습니다. 로딩 약 11.7초, 임의 여섯 위치 탐색 총 약 0.036초, 프로세스 최대 RSS 약 240MiB였습니다. 이는 해당 환경의 관측값이며 일반 성능 보장은 아닙니다. 실제 데스크톱에서 마우스로 조작하는 수동 검증은 별도로 필요합니다.
