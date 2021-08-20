# Auto-generated from R7-2-1-20-gda3bfab4
# May not be backward/forward-compatible or 100% accurate

from dataclasses import dataclass
from typing import ClassVar, Dict

from . import asyn
from .common import AsynPortBase, ShellStateHandler

_handler = ShellStateHandler.generic_handler_decorator


@dataclass
class MotorState(ShellStateHandler):
    """Motor record support IOC shell state handler / container."""

    metadata_key: ClassVar[str] = "motor"

    @property
    def asyn(self) -> asyn.AsynState:
        """Asyn instance."""
        if self.primary_handler is None:
            raise RuntimeError("Requires a primary handler")
        return self.primary_handler.asyn

    @property
    def ports(self) -> Dict[str, AsynPortBase]:
        """Asyn ports."""
        return self.asyn.ports

    @_handler(stub=True)
    def handle_A3200AsynConfig(
        self,
        card_being_configured: int,
        asyn_port_name: str,
        asyn_address_gpib: int,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
        task_number: int,
        linear_move_commands: int,
    ):
        ...

    @_handler(stub=True)
    def handle_A3200AsynSetup(self, max_controller_count: int):
        ...

    @_handler(stub=True)
    def handle_ACRCreateController(
        self,
        port_name: str,
        acr_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_AG_CONEXCreateController(
        self,
        port_name: str,
        serial_port_name: str,
        controller_id: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_AG_UCCreateAxis(
        self,
        controller_port_name: str,
        axis_number: int,
        has_limits: int,
        forward_amplitude: int,
        reverse_amplitude: int,
    ):
        ...

    @_handler(stub=True)
    def handle_AG_UCCreateController(
        self,
        port_name: str,
        serial_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_ANC150AsynConfig(
        self,
        card_being_configured: int,
        asyn_port_name: str,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
    ):
        ...

    @_handler(stub=True)
    def handle_ANC150AsynSetup(self, maximum_of_controllers: int):
        ...

    @_handler(stub=True)
    def handle_ANF2CreateAxis(
        self,
        port_name: str,
        axis_number: int,
        hex_config: str,
        base_speed: int,
        homing_timeout: int,
    ):
        ...

    @_handler(stub=True)
    def handle_ANF2CreateController(
        self,
        port_name: str,
        anf2_in_port_name: str,
        anf2_out_port_name: str,
        number_of_axes: int,
    ):
        ...

    @_handler(stub=True)
    def handle_ANF2StartPoller(
        self, port_name: str, moving_poll_period_ms: int, idle_poll_period_ms: int
    ):
        ...

    @_handler(stub=True)
    def handle_ANG1CreateController(
        self,
        port_name: str,
        ang1_in_port_name: str,
        ang1_out_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_AcsMotionConfig(
        self,
        acs_port_name: str,
        asyn_port_name: str,
        num_axes: int,
        moving_polling_rate: float,
        idle_polling_rate: float,
    ):
        ...

    @_handler(stub=True)
    def handle_C300CreateController(
        self,
        port_name: str,
        c300_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_EMC18011Config(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_EMC18011Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_ESP300Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_ESP300Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_EnsembleAsynConfig(
        self,
        card_being_configured: int,
        asyn_port_name: str,
        asyn_address_gpib: int,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
    ):
        ...

    @_handler(stub=True)
    def handle_EnsembleAsynSetup(self, max_controller_count: int):
        ...

    @_handler(stub=True)
    def handle_HXPCreateController(
        self,
        port_name: str,
        ip_address: str,
        port: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_Hytec8601Configure(
        self,
        port_name: str,
        num_axes: int,
        moving_poll_period: int,
        idle_poll_period: int,
        cardnum: int,
        carrier: int,
        ipslot: int,
        vector: int,
        useencoder: int,
        encoder_ratio0: float,
        encoder_ratio1: float,
        encoder_ratio2: float,
        encoder_ratio3: float,
    ):
        ...

    @_handler(stub=True)
    def handle_IM483PLConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_IM483PLSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_IM483SMConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_IM483SMSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_ImsMDrivePlusCreateController(
        self,
        motor_port_name: str,
        io_port_name: str,
        device_name: str,
        moving_poll_period_ms: float,
        idle_poll_period_ms: float,
    ):
        ...

    @_handler(stub=True)
    def handle_LinmotCreateController(
        self,
        port_name: str,
        linmot_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MAXvConfig(
        self,
        card_being_configured: int,
        configuration_string: str,
        absolute_encoder_flags: int,
        grey_code_flags: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MAXvSetup(
        self,
        max_controller_count: int,
        vme_address_type: int,
        base_address_on_4_k_0x1000_boundary: int,
        valid_vectors: int,
        interrupt_level_1_6: int,
        polling_rate_hz: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MCB4BConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_MCB4BCreateController(
        self,
        port_name: str,
        mcb_4_b_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MCB4BSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MCDC2805Config(
        self,
        card_being_configured: int,
        modules_on_this_serial_port: int,
        asyn_port_name: str,
    ):
        ...

    @_handler(stub=True)
    def handle_MCDC2805Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MCS2CreateController(
        self,
        port_name: str,
        mcs2_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MDT695Config(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_MDT695Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MDriveConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_MDriveSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MM3000Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_MM300Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MM4000AsynConfig(
        self,
        card_being_configured: int,
        asyn_port_name: str,
        asyn_address_gpib: int,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MM4000AsynSetup(self, max_controller_count: int):
        ...

    @_handler(stub=True)
    def handle_MM4000Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_MM4000Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MMC200CreateController(
        self,
        port_name: str,
        mmc_200_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
        ignore_limit_flag: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MVP2001CreateAxis(
        self,
        controller_port_name: str,
        axis_number: int,
        encoder_lines_per_rev: int,
        max_current_ma: int,
        limit_polarity: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MVP2001CreateController(
        self,
        port_name: str,
        mvp_2001_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_MXmotorSetup(self, max_motor: int, mx_data_file: str, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_MicosConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_MicosSetup(
        self, max_controller_count: int, max_motor_count: int, polling_rate: int
    ):
        ...

    @_handler(stub=True)
    def handle_MicroMoConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_MicroMoSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_OmsPC68Config(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_OmsPC68Setup(self, maximum_of_cards: int, polling_rate_hz: int):
        ...

    @_handler(stub=True)
    def handle_PC6KConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_PC6KSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PC6KUpLoad(
        self,
        controller_card: int,
        upload_file_path: str,
        program_name_null_immediate: str,
    ):
        ...

    @_handler(stub=True)
    def handle_PIC630Config(
        self,
        card_being_configured: int,
        asyn_port_name: str,
        ch_1_current_setting: int,
        ch_2_current_setting: int,
        ch_3_current_setting: int,
        ch_4_current_setting: int,
        ch_5_current_setting: int,
        ch_6_current_setting: int,
        ch_7_current_setting: int,
        ch_8_current_setting: int,
        ch_9_current_setting: int,
    ):
        ...

    @_handler(stub=True)
    def handle_PIC630Setup(
        self, max_controller_groups: int, max_axes_per_group: int, polling_rate: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIC662Config(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_PIC662Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIC663Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIC663Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIC844Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIC844Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIC848Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIC848Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIC862Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIC862Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIE516Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIE516Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIE517Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIE517Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIE710Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIE710Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIE816Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIE816Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PIJEDSConfig(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PIJEDSSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PI_GCS2_CreateController(
        self,
        port_name: str,
        asyn_port_name: str,
        number_of_axes: int,
        priority: int,
        stack_size: int,
        moving_polling_time_msec: int,
        idle_polling_time_msec: int,
    ):
        ...

    @_handler(stub=True)
    def handle_PM304Config(
        self, card_being_configured: int, asyn_port_name: str, number_of_axes: int
    ):
        ...

    @_handler(stub=True)
    def handle_PM304Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PM500Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PM500Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_PMNC87xxConfig(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_PMNC87xxSetup(
        self,
        max_controller_count: int,
        max_drivers_per_controller_count: int,
        polling_rate: int,
    ):
        ...

    @_handler(stub=True)
    def handle_SC800Config(
        self, card_being_configured: int, asyn_port_name: str, asyn_address_gpib: int
    ):
        ...

    @_handler(stub=True)
    def handle_SC800Setup(self, maximum_of_cards: int, polling_rate_hz: int):
        ...

    @_handler(stub=True)
    def handle_SMC100Config(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_SMC100CreateController(
        self,
        port_name: str,
        smc100_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
        eg_us_per_step: str,
    ):
        ...

    @_handler(stub=True)
    def handle_SMC100Setup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_SMCcorvusChangeResolution(
        self, smc_corvus_port_name: str, axis_number: int, axis_resolution: float
    ):
        ...

    @_handler(stub=True)
    def handle_SMCcorvusCreateController(
        self,
        port_name: str,
        smc_corvus_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_SMChydraChangeResolution(
        self, smc_hydra_port_name: str, axis_number: int, axis_resolution: float
    ):
        ...

    @_handler(stub=True)
    def handle_SMChydraCreateController(
        self,
        port_name: str,
        smc_hydra_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_SPiiPlusConfig(
        self,
        card_being_configured: int,
        asyn_port_name: str,
        command_mode_bu_ffer_co_nnect_di_rect: str,
    ):
        ...

    @_handler(stub=True)
    def handle_SPiiPlusSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_ScriptAxisConfig(
        self, controller_port_name: str, axis_number: int, parameters: str
    ):
        ...

    @_handler(stub=True)
    def handle_ScriptControllerConfig(
        self,
        motor_port_name: str,
        number_of_axes: int,
        control_script: str,
        parameters: str,
    ):
        ...

    @_handler(stub=True)
    def handle_ScriptMotorReload(self, motor_port_name: str):
        ...

    @_handler(stub=True)
    def handle_SmartMotorConfig(self, card_being_configured: int, asyn_port_name: str):
        ...

    @_handler(stub=True)
    def handle_SmartMotorSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_SoloistConfig(
        self, card_being_configured: int, asyn_port_name: str, asyn_address: int
    ):
        ...

    @_handler(stub=True)
    def handle_SoloistSetup(self, max_controller_count: int, polling_rate: int):
        ...

    @_handler(stub=True)
    def handle_XPSAuxConfig(
        self, port_name: str, ip_address: str, ip_port: int, polling_period: int
    ):
        ...

    @_handler(stub=True)
    def handle_XPSConfig(
        self,
        card_being_configured: int,
        ip: str,
        port: int,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
    ):
        ...

    @_handler(stub=True)
    def handle_XPSConfigAxis(
        self,
        card_number: int,
        axis_number: int,
        axis_name: str,
        steps_per_unit: str,
        no_disabled_error: int,
    ):
        ...

    @_handler(stub=True)
    def handle_XPSCreateAxis(
        self,
        controller_port_name: str,
        axis_number: int,
        axis_name: str,
        steps_per_unit: str,
    ):
        ...

    @_handler(stub=True)
    def handle_XPSCreateController(
        self,
        controller_port_name: str,
        ip_address: str,
        ip_port: int,
        number_of_axes: int,
        moving_poll_rate_ms: int,
        idle_poll_rate_ms: int,
        enable_set_position: int,
        set_position_settling_time_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_XPSCreateProfile(
        self,
        controller_port_name: str,
        max_points: int,
        ftp_username: str,
        ftp_password: str,
    ):
        ...

    @_handler(stub=True)
    def handle_XPSDisableAutoEnable(self, controller_port_name: str):
        ...

    @_handler(stub=True)
    def handle_XPSDisablePoll(self, set_disable_poll_value: int):
        ...

    @_handler(stub=True)
    def handle_XPSEnableMoveToHome(
        self, card_number: int, axis_name: str, distance: int
    ):
        ...

    @_handler(stub=True)
    def handle_XPSEnableMovingMode(self, controller_port_name: str):
        ...

    @_handler(stub=True)
    def handle_XPSEnableSetPosition(self, set_position_flag: int):
        ...

    @_handler(stub=True)
    def handle_XPSGathering(self, interelement_period: int):
        ...

    @_handler(stub=True)
    def handle_XPSInterpose(self, port_name: str):
        ...

    @_handler(stub=True)
    def handle_XPSNoDisableError(self, controller_port_name: str):
        ...

    @_handler(stub=True)
    def handle_XPSSetPosSleepTime(self, set_position_sleep_time: int):
        ...

    @_handler(stub=True)
    def handle_XPSSetup(self, number_of_xps_controllers: int):
        ...

    @_handler(stub=True)
    def handle_asynMotorEnableMoveToHome(
        self, controller_port_name: str, axis_number: int, distance: int
    ):
        ...

    @_handler(stub=True)
    def handle_listMovingMotors(self, list_moving_motors: str):
        ...

    @_handler(stub=True)
    def handle_motorSimConfigAxis(
        self,
        post_name: str,
        axis: int,
        high_limit: int,
        low_limit: int,
        home_position: int,
        start_posn: int,
    ):
        ...

    @_handler(stub=True)
    def handle_motorSimCreate(
        self,
        card: int,
        signal: int,
        high_limit: int,
        low_limit: int,
        home_position: int,
        num_cards: int,
        num_signals: int,
        start_posn: int,
    ):
        ...

    @_handler(stub=True)
    def handle_motorSimCreateController(
        self, port_name: str, number_of_axes: int, priority: int, stack_size: int
    ):
        ...

    @_handler(stub=True)
    def handle_motorUtilInit(self, ioc_name: str):
        ...

    @_handler(stub=True)
    def handle_nf874xCreateController(
        self,
        port_name: str,
        nf874x_port_name: str,
        number_of_axes: int,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
    ):
        ...

    @_handler(stub=True)
    def handle_oms58Setup(
        self, num_card: int, addrs: int, vector: int, int_level: int, scan_rate: int
    ):
        ...

    @_handler(stub=True)
    def handle_omsMAXnetConfig(
        self,
        asyn_motor_port_name: str,
        number_of_axes: int,
        asyn_serial_tcp_port_name: str,
        moving_poll_rate: int,
        idle_poll_rate: int,
        initstring: str,
    ):
        ...

    @_handler(stub=True)
    def handle_omsMAXvConfig(
        self,
        number_of_card: int,
        asyn_motor_port_name: str,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
        initstring: str,
    ):
        ...

    @_handler(stub=True)
    def handle_omsMAXvConfig2(
        self,
        slot_number: int,
        address_type_a16_a24_a32: str,
        board_address_on_4_k_0x1000_boundary: int,
        interrupt_vector_noninterrupting_0_64_255: int,
        interrupt_level_1_6: int,
        asyn_motor_port_name: str,
        number_of_axes: int,
        task_priority_0_medium: int,
        stack_size_0_medium: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
        initstring: str,
    ):
        ...

    @_handler(stub=True)
    def handle_omsMAXvEncFuncConfig(
        self,
        number_of_card: int,
        asyn_motor_port_name: str,
        number_of_axes: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
        initstring: str,
    ):
        ...

    @_handler(stub=True)
    def handle_omsMAXvEncFuncConfig2(
        self,
        slot_number: int,
        address_type_a16_a24_a32: str,
        board_address_on_4_k_0x1000_boundary: int,
        interrupt_vector_noninterrupting_0_64_255: int,
        interrupt_level_1_6: int,
        asyn_motor_port_name: str,
        number_of_axes: int,
        task_priority_0_medium: int,
        stack_size_0_medium: int,
        moving_poll_rate: int,
        idle_poll_rate: int,
        initstring: str,
    ):
        ...

    @_handler(stub=True)
    def handle_omsMAXvSetup(
        self,
        max_controller_count: int,
        vme_address_type: int,
        base_address_on_4_k_0x1000_boundary: int,
        noninterrupting_0_valid_vectors_64_255: int,
        interrupt_level_1_6: int,
    ):
        ...

    @_handler(stub=True)
    def handle_phytronCreateAxis(
        self, controller_name: str, module_index: int, axis_index: int
    ):
        ...

    @_handler(stub=True)
    def handle_phytronCreateController(
        self,
        port_name: str,
        phytron_axis_port_name: str,
        moving_poll_period_ms: int,
        idle_poll_period_ms: int,
        timeout_ms: float,
    ):
        ...

    @_handler(stub=True)
    def handle_printChIDlist(self, print_motor_util_chid_list: str):
        ...

    @_handler(stub=True)
    def handle_setIdlePollPeriod(self, controller_port_name: str, axis_number: float):
        ...

    @_handler(stub=True)
    def handle_setMovingPollPeriod(self, controller_port_name: str, axis_number: float):
        ...

    @_handler(stub=True)
    def handle_smarActMCSCreateAxis(
        self, controller_port_name_string: str, axis_number_int: int, channel_int: int
    ):
        ...

    @_handler(stub=True)
    def handle_smarActMCSCreateController(
        self,
        port_name_string: str,
        i_o_port_name_string: str,
        number_of_axes_int: int,
        moving_poll_period_s_double: float,
        idle_poll_period_s_double: float,
    ):
        ...

    @_handler(stub=True)
    def handle_smarActSCUCreateAxis(
        self, controller_port_name_string: str, axis_number_int: int, channel_int: int
    ):
        ...

    @_handler(stub=True)
    def handle_smarActSCUCreateController(
        self,
        port_name_string: str,
        i_o_port_name_string: str,
        number_of_axes_int: int,
        moving_poll_period_s_double: float,
        idle_poll_period_s_double: float,
    ):
        ...

    @_handler(stub=True)
    def handle_tclcall(self, tcl_name: str, task_name: str, function_args: str):
        ...

    @_handler(stub=True)
    def handle_xps_gathering(self, element_period_10_4: int):
        ...

    @_handler(stub=True)
    def handle_EthercatMCCreateAxis(
        self, motor_port: str, axis_num: int, amplifier_flags: str, axis_config: str
    ):
        ...

    @_handler
    def handle_adsAsynPortDriverConfigure(
        self,
        portName: str,
        ipaddr: str = "",
        amsaddr: str = "",
        amsport: int = 0,
        asynParamTableSize: int = 0,
        priority: int = 0,
        noAutoConnect: int = 0,
        defaultSampleTimeMS: int = 0,
        maxDelayTimeMS: int = 0,
        adsTimeoutMS: int = 0,
        defaultTimeSource: str = "",
    ):
        # SLAC-specific, but doesn't hurt anyone
        self.ports[portName] = asyn.AdsAsynPort(
            context=self.get_load_context(),
            name=portName,
            ipaddr=ipaddr,
            amsaddr=amsaddr,
            amsport=amsport,
            asynParamTableSize=asynParamTableSize,
            priority=priority,
            noAutoConnect=noAutoConnect,
            defaultSampleTimeMS=defaultSampleTimeMS,
            maxDelayTimeMS=maxDelayTimeMS,
            adsTimeoutMS=adsTimeoutMS,
            defaultTimeSource=defaultTimeSource,
        )

    @_handler
    def handle_drvAsynMotorConfigure(
        self,
        port_name: str = "",
        driver_name: str = "",
        card_num: int = 0,
        num_axes: int = 0,
    ):
        self.ports[port_name] = asyn.AsynMotor(
            context=self.get_load_context(),
            name=port_name,
            parent=None,
            metadata=dict(
                num_axes=num_axes,
                card_num=card_num,
                driver_name=driver_name,
            ),
        )

    @_handler
    def handle_EthercatMCCreateController(
        self,
        motor_port: str,
        asyn_port: str,
        num_axes: int = 0,
        move_poll_rate: float = 0.0,
        idle_poll_rate: float = 0.0,
    ):
        # SLAC-specific
        port = self.ports[asyn_port]
        motor = asyn.AsynMotor(
            context=self.get_load_context(),
            name=motor_port,
            parent=asyn_port,
            metadata=dict(
                num_axes=num_axes,
                move_poll_rate=move_poll_rate,
                idle_poll_rate=idle_poll_rate,
            ),
        )

        # Tie it to both the original asyn port (as a motor) and also the
        # top-level asyn ports.
        port.motors[motor_port] = motor
        self.ports[motor_port] = motor
