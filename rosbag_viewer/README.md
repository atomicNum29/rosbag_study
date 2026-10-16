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

## 여러 카메라 · 라이다 · 속도 명령

```bash
uv run python -m rosbag_viewer rosbag_data/rosbag_2026-10-15_1/
```

상단 센서 영역은 카메라와 라이다를 함께 배치하는 **2D views**입니다. **Visible views**에서 카메라·라이다 토픽을 각각 선택하면 같은 영역에 동시에 표시합니다. 기본은 기준 카메라와 라이다이며, **Show all / Hide all**로 전체 선택·해제하고 **1~3 columns**로 열 수를 바꿀 수 있습니다. 뷰가 많으면 스크롤하거나 센서 영역 높이를 늘려 볼 수 있습니다. 하단 시간 슬라이더, 그래프 cursor, 재생·일시정지로 모든 센서를 같은 시각에 탐색합니다. 센서 영역과 그래프 사이의 경계선을 드래그해 높이를 조절할 수 있습니다.

### 카메라

bag의 모든 `sensor_msgs/msg/Image` / `sensor_msgs/msg/CompressedImage` 토픽을 자동으로 읽습니다. 새 bag의 `/front_camera/image_raw`, `/rear_camera/image_raw`, `/camera/fisheye1/image_raw`를 모두 볼 수 있습니다.

- **Frame-step camera**: 이전/다음 프레임 이동의 기준을 선택합니다. 화면에 표시할 토픽은 `Visible views`에서 별도로 선택합니다. `--image-topic`은 처음 선택할 카메라이며, 다른 카메라의 로딩을 제한하지 않습니다. 지정 카메라가 없으면 사용 가능한 카메라를 선택하고 상태 표시줄에 알립니다.
- **Visible views → Show all**: 모든 카메라와 라이다를 같은 그리드에 표시합니다. 동시 보기에서도 프레임 이동 기준은 선택한 카메라입니다.
- 각 카메라는 현재 시각 이하의 가장 최근 프레임을 독립적으로 선택하므로 서로 다른 FPS를 지원합니다. 첫 프레임 이전에는 빈 화면입니다.
- 영상 위의 `Frame`은 상대 센서 timestamp, `age`는 현재 시각과의 차이입니다. 마지막 영상 이후에는 마지막 프레임과 증가하는 age가 표시됩니다.

### 라이다

`/scan` (`sensor_msgs/msg/LaserScan`)이 있으면 `Visible views`에 **Lidar · /scan** 항목이 추가됩니다. 각 ray의 `angle_min + i × angle_increment`와 range를 이용해 센서 기준 `X=r cos(angle)`, `Y=r sin(angle)` 점을 그립니다. 화면의 **세로축은 X(전방 +X가 위쪽), 가로축은 Y(+Y가 왼쪽)**이며 원점은 빨간 십자입니다. NaN/Inf 및 `range_min`~`range_max` 밖의 값은 제외합니다.

**Flip scan orientation (Y → −Y)**를 켜면 Y 부호를 반전하여 화면의 좌우를 뒤집습니다. +X가 위를 향하는 방향은 유지됩니다. Z 방향이 반대인 설치에서 표시 방향을 바꿔 비교할 수 있으며, 원본 스캔은 변경하지 않습니다. 이는 2D 표시 반전이며 임의 장착 각도의 TF 보정은 아닙니다. 반전 선택은 bag을 다시 열어도 현재 앱 실행 중에는 유지됩니다.

센서 `frame_id`, 유효 ray 수, 스캔 시각과 age를 표시합니다. 스캔도 현재 시각 이하의 가장 최근 메시지를 선택하며, 첫 스캔 전에는 빈 화면입니다. 첫 스캔에서 범위를 맞춘 뒤 마우스로 확대·이동할 수 있습니다. XY축은 같은 축척을 사용합니다. `header.stamp`는 첫 ray 획득 시각이며, ray별 시간 보정·이동 왜곡 보정·TF 변환·지도 누적은 수행하지 않습니다. [LaserScan 메시지 정의](https://github.com/ros2/common_interfaces/blob/rolling/sensor_msgs/msg/LaserScan.msg)

### 속도 명령

`/cmd_vel`이 있으면 **Command** 탭에 선속도 X/Y/Z[m/s]와 각속도 X/Y/Z[rad/s]를 추가합니다. 이 계열은 **All / Compare**, **Custom Compare**에서도 선택할 수 있어 휠 RPM이나 IMU와 비교할 수 있습니다. `Twist`는 header가 없어 record timestamp를 사용하며 `TwistStamped`는 기존 timestamp 선택 규칙을 적용합니다.

```bash
uv run python -m rosbag_viewer /path/to/bag --scan-topic /lidar/scan --cmd-vel-topic /robot/cmd_vel
# 해당 센서 읽기 제외
uv run python -m rosbag_viewer /path/to/bag --no-scan --no-cmd-vel
```

카메라와 라이다는 각각 임시 디스크 파일과 시간 인덱스를 사용합니다. 영상 전체를 디코딩해 RAM에 올리지 않으며, 기본 64MiB 영상 캐시 예산을 카메라 수로 나눠 사용합니다. 라이다는 마지막으로 디코딩한 스캔 하나만 보관합니다. 표시용 Qt 이미지와 MCAP reader 버퍼는 별도 메모리를 사용합니다. 임시 디스크 공간은 모든 영상·스캔의 직렬화 바이트 크기만큼 필요합니다. bag 재열기 시 다시 생성하며 종료·로딩 취소·실패 시 정리합니다.

## 밝은 테마와 그래프 구성

전체 UI는 운영체제의 다크 모드와 무관하게 밝은 테마를 사용하며, 그래프 배경은 흰색입니다. 범례는 그래프 위의 별도 줄에 표시되어 데이터를 가리지 않습니다. 범례 체크박스로 각 축/바퀴의 선을 개별적으로 켜고 끌 수 있습니다.

- **IMU**: gyro / accel
- **Wheels**: 네 바퀴 RPM / 전류[A]
- **Motor**: 네 바퀴 제어 출력[raw] / 드라이버 A·B 전압[V]
- **Pose**: 위치 X/Y/Z[m] / 자세 roll·pitch·yaw[rad] (토픽이 있는 경우)
- **All / Compare**: 모든 센서 그래프를 한 화면에서 스크롤하며 비교
- **Custom Compare**: 데이터 계열을 선택해 한 좌표평면에 겹치거나 두 좌표평면에 나누어 표시

`Visible graphs` 메뉴에서 필요한 그래프만 남길 수 있습니다. 예를 들어 All / Compare에서 gyro와 Wheel RPM만 선택하면 함께 비교할 수 있습니다. `Show 2D views`를 끄면 그래프 공간을 넓힐 수 있습니다. 모든 탭의 시간축 확대·이동 및 현재 시각은 동기화됩니다. 그래프가 많아도 영상과 하단 재생 컨트롤은 스크롤되지 않습니다. bag을 다시 열면 그래프 선택은 초기화됩니다.

### 원하는 데이터를 같은 좌표평면에 그리기

1. **Custom Compare** 탭을 엽니다.
2. 상단에서 **1 plot / 2 plots**를 선택합니다.
3. 왼쪽 목록에서 원하는 데이터의 **1 / 2 열 체크박스**를 켭니다. 예를 들어 `Pose orientation / yaw`와 `Gyroscope / z`를 1열에, 앞왼쪽·앞오른쪽 RPM을 2열에 선택합니다. 같은 데이터를 두 평면에 동시에 선택해도 됩니다.
4. 각 평면에서 **Original values** 또는 **Normalize each series 0–1**을 선택합니다.

X축은 공통 시간[s]이며, Y축에 선택한 데이터를 겹쳐 표시합니다. 센서마다 원래 timestamp 배열을 그대로 사용하므로 서로 다른 샘플링 속도를 강제로 보간하지 않습니다. 좌표평면별로 하나의 Y축을 공유하며, 원래 단위가 섞이면 `Mixed units · see legend`로 표시합니다. 별도의 오른쪽 Y축은 사용하지 않습니다. 크기가 매우 다른 값을 비교할 때는 평면을 나누거나 정규화를 사용하세요.

정규화는 **각 데이터 계열의 전체 로그 구간**에서 최솟값을 0, 최댓값을 1로 변환합니다. 확대 구간이 바뀌어도 기준은 유지됩니다. 상수 계열은 0, 결측·유효하지 않은 샘플은 빈 구간으로 표시합니다. 저장된 원본 값과 기본 탭 그래프는 바뀌지 않습니다. 범례는 평면 위에 표시하며 계열명과 원래 단위를 함께 보여줍니다.

검색은 목록만 필터링하고 이미 그린 선을 해제하지 않습니다. `Clear selections`로 두 평면의 선택을 모두 초기화합니다. 2→1→2 평면 전환에서는 두 번째 평면의 선택이 유지됩니다. bag을 새로 열면 선택이 초기화됩니다. 이 탭의 선택은 기존 `Visible graphs` 메뉴와 독립적입니다. cursor 탐색·재생·X축 확대 범위는 기존 그래프와 모두 동기화됩니다.

### Pose 자동 인식

기본 `/camera/pose/sample`이 있으면 **Pose position**과 **Pose orientation** 그래프를 추가합니다. 지원 타입은 `nav_msgs/msg/Odometry`, `geometry_msgs/msg/PoseStamped`, `geometry_msgs/msg/PoseWithCovarianceStamped`입니다. 기존 bag에 pose가 없으면 해당 탭 없이 정상 동작합니다.

```bash
uv run python -m rosbag_viewer rosbag_data/rosbag_2026-09-17_2/
# 다른 pose 토픽을 지정하거나 읽지 않기
uv run python -m rosbag_viewer /path/to/bag --pose-topic /odom
uv run python -m rosbag_viewer /path/to/bag --no-pose
```

위치는 메시지의 원래 기준 좌표계에서 X/Y/Z[m]를 표시합니다. TF 변환이나 시작 위치 제거는 하지 않습니다. 기록된 quaternion(x,y,z,w)을 정규화해 고정 X/Y/Z축 roll/pitch/yaw[rad]로 변환합니다. ROS 좌표 관례는 [REP 103](https://reps.openrobotics.org/rep-0103/)을 따릅니다. 각도는 principal range로 표시하므로 roll/yaw의 ±π 경계에서 점프가 있을 수 있으며 unwrap하지 않습니다. pitch ±π/2에서는 Euler 표현이 유일하지 않아 roll=0인 동등한 표현을 사용합니다. 영벡터 또는 유한하지 않은 quaternion은 빈 구간입니다. timestamp는 다른 센서와 동일한 header 우선/record 대체 규칙을 사용합니다.

### 휠 데이터 자동 인식

`/motor_bridge_node/status` (`std_msgs/msg/String`)가 있으면 motor bridge JSON 텔레메트리를 자동으로 읽습니다. 이 토픽이 없는 기존 bag도 그대로 열 수 있습니다.

```bash
uv run python -m rosbag_viewer rosbag_data/rosbag_2026-09-17_2/
# 다른 토픽 이름
uv run python -m rosbag_viewer /path/to/bag --motor-topic /custom/status
# 모터 데이터 제외
uv run python -m rosbag_viewer /path/to/bag --no-motor
```

실제 기록 형식에 맞춘 매핑은 `config.py`의 `motor_series()`에 있습니다.

| 그래프 | JSON 필드 | 변환 |
| --- | --- | --- |
| RPM | `wheels.{lf,rf,lr,rr}.rpm` | 원래 RPM |
| 전류 | `wheels.{lf,rf,lr,rr}.current_deci_amp` | ×0.1 → A |
| 제어 출력 | `wheels.{lf,rf,lr,rr}.controller_output` | 원시값; 퍼센트로 추정하지 않음 |
| 전압 | `drivers.{a,b}.voltage_mv` | ×0.001 → V |

LF/RF/LR/RR는 각각 앞왼쪽/앞오른쪽/뒤왼쪽/뒤오른쪽입니다. `valid`가 false이거나 필드가 없으면 NaN으로 두어 선을 끊습니다. 잘못된 JSON 메시지도 빈 구간으로 두고 상태 표시줄에 횟수를 알립니다. JSON은 메시지당 한 번 파싱합니다.

String에는 센서 header가 없으므로 **bag record timestamp**로 카메라·IMU와 동기화합니다. 상태 표시줄의 record timestamp 사용 횟수는 이 토픽에서 정상적으로 표시됩니다. 센서의 전송 지연 자체를 보정하지는 않습니다.

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
- 공통 0초는 **읽어 들인 모든 카메라·라이다·시계열 메시지의 최소 유효 timestamp**입니다. header 모드에서는 metadata의 record 시작 시각과 다를 수 있습니다. 표시 범위도 선택한 데이터의 끝까지입니다.
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

seek에서는 `np.searchsorted(..., side="right") - 1`로 프레임을 찾고, 파일 offset으로 직접 읽어 `cv_bridge`로 RGB 변환합니다. 읽은 프레임은 전체 카메라 합계 기본 최대 64 MiB LRU 캐시에 보관합니다(예산을 카메라 수로 균등 분할). 단일 프레임이 예산보다 크면 표시만 하고 캐시에 넣지 않습니다. mono8, mono16, RGB/BGR 등 cv_bridge가 RGB8로 변환할 수 있는 Image encoding을 지원합니다. mono16은 고정 16→8bit 스케일로 표시합니다.

이 버전은 **MCAP 자체의 chunk index를 seek에 사용하지 않는 디스크 인덱스 방식**입니다. 압축된 MCAP보다 큰 임시 공간이 필요할 수 있으며, 원시 직렬화 이미지 및 스캔 전체 크기만큼 디스크를 사용합니다. `--temp-dir`로 충분한 공간이 있는 디스크를 선택하세요. 파일은 닫기, 재열기, 로딩 실패/취소 시 정리합니다. 디스크 공간 부족은 로딩 오류로 표시됩니다. 최초 스캔은 전체 길이에 비례하며 재실행 시 다시 수행합니다.

Qt timer는 약 60 Hz로 UI를 갱신하고, 재생 위치는 monotonic clock의 경과 시간 × 재생속도로 계산합니다. 느린 갱신에서 프레임을 건너뛰어 시간 흐름을 유지합니다. 단일 프레임 읽기/디코딩은 GUI 스레드에서 실행하므로 매우 큰 프레임이나 느린 디스크에서는 잠깐 지연될 수 있습니다. cursor/slider의 프로그램 갱신은 `QSignalBlocker`로 감싸 피드백 루프를 방지합니다.

## 파일 역할과 확장

| 파일 | 역할 |
| --- | --- |
| `config.py` | 기본 토픽, timestamp 모드, 캐시 예산, `SeriesSpec` |
| `data.py` | `BagDataSource`, `TimeSeriesData` (`ImuData` 별칭), `ImageSource`, 디스크 인덱스와 LRU |
| `playback.py` | monotonic clock 재생, 공통 seek, 프레임 이동, 시간 포맷 |
| `window.py` | 비동기 로딩, 영상, 그룹 탭·비교 화면, 외부 범례, 컨트롤, 이벤트 동기화 |
| `theme.py` | 밝은 Qt 팔레트 |
| `media.py` | 여러 카메라 선택·동시 보기, LaserScan XY 표시·Y 반전 |
| `plots.py` | 공유 시간축 그래프, 밝은 축 스타일, seek cursor |
| `comparison.py` | 채널별 1·2 평면 선택, 외부 범례, 정규화와 겹쳐 그리기 |
| `main.py`, `__main__.py` | CLI 및 앱 진입점 |
| `tests/test_viewer.py` | ROS 없이 수행하는 코어 및 offscreen GUI 회귀 테스트 |
| `tests/test_comparison.py` | quaternion/RPY 변환, 사용자 비교 평면 선택·정규화·동기화 |
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

필드는 점으로 구분된 숫자 속성 및 `data[0]` 같은 배열 인덱스를 지원합니다. `SeriesSpec.group`으로 탭, `scales`로 필드별 단위 배율, `payload="json"`으로 JSON 필드 접근, `validity_fields`로 값의 유효성 필드를 지정할 수 있습니다. 복합 변환이 필요한 타입은 별도 extractor 확장이 필요합니다.

## 검증

```bash
source /opt/ros/jazzy/setup.bash
uv run python -m unittest discover -s rosbag_viewer/tests -v
```

GUI 테스트는 offscreen 모드로 실행합니다. ROS가 없으면 MCAP 통합 테스트는 skip됩니다. 테스트는 중복/역순 timestamp, 공통 IMU 토픽, record 시간 보존, 이미지 직접 읽기와 캐시 제한, 실제 시간 기반 재생과 속도 변경, 끝 도달, frame step 및 slider/cursor 이벤트 동기화를 확인합니다.

API 참고: [rosbag2 SequentialReader 테스트](https://github.com/ros2/rosbag2/blob/rolling/rosbag2_py/test/test_sequential_reader.py), [Qt QSignalBlocker](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSignalBlocker.html).

이 작업 환경에서 ROS Jazzy를 source한 상태로 6개 테스트를 통과했습니다. 기존 `/home/cu/rosbag_2026-09-12_2` (3.5GB)를 offscreen GUI로 열어 영상 2,689개, gyro 17,923개, accel 5,553개, 상대시간 약 89.681초를 확인했습니다. 로딩 약 11.7초, 임의 여섯 위치 탐색 총 약 0.036초, 프로세스 최대 RSS 약 240MiB였습니다. 이는 해당 환경의 관측값이며 일반 성능 보장은 아닙니다. 실제 데스크톱에서 마우스로 조작하는 수동 검증은 별도로 필요합니다.

2026-09-17 확장 검증: `rosbag_data/rosbag_2026-09-17_2/`를 offscreen GUI에서 열어 영상 6,990개 및 motor 상태 23,301개를 확인했습니다. 4개 모터 그래프의 실제 값 범위는 RPM -173~229, 전류 0~5.7A, 제어 출력 -2421~2971, 전압 25.9~26.8V였습니다. 단위 변환·유효성 처리·잘못된 JSON·토픽 자동 인식/비활성화·탭 이동·비교 화면·선/그래프 숨김·탭 사이 시간축 동기화 테스트를 추가했습니다.

2026-09-19 확장 검증: 동일한 bag의 pose 46,596개를 로드해 위치·RPY 배열과 8개 기본 그래프를 확인했습니다. offscreen GUI에서 pose yaw/gyro z 오버레이 및 두 바퀴 RPM 비교를 서로 다른 평면에 배치하고 공통 시간축을 검증했습니다. 전체 14개 테스트에는 pose 자동 인식·비활성화, quaternion 정규화·잘못된 값·특이 자세, 독립 평면 선택과 정규화, 원본 timestamp 보존, custom cursor seek 및 X축 동기화가 포함됩니다.

2026-10-15 검증: `rosbag_data/rosbag_2026-10-15_1/`(약 25GB)를 offscreen GUI로 열어 전방 9,009개, 후방 8,986개, fisheye 13,410개 영상, LaserScan 5,474개, cmd_vel 6,307개를 확인했습니다. 해당 환경에서 로딩 약 108초, 최대 RSS 약 321MiB였습니다. 총 18개 테스트에는 raw/압축 영상 직접 읽기, 카메라 전환·동시 보기·프레임 이동, 스캔 범위 필터·시간 탐색·Y 반전, Twist/TwistStamped 시간·필드 매핑 및 임시 파일 정리가 포함됩니다.
